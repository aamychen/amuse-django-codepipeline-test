import logging

from Adyen.exceptions import AdyenAPIResponseError
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.signing import TimestampSigner
from django.urls import reverse
from django.utils import timezone

from amuse.utils import (
    CLIENT_ANDROID,
    FakePhoneNumberError,
    InvalidPhoneNumberError,
    format_phonenumber,
)
from amuse.vendor.adyen.vat import calculate_vat
from amuse.vendor.adyen.exceptions import (
    CheckoutError,
    PaymentActionResponse,
    PaymentCancelledResponse,
    PaymentErrorResponse,
    PaymentPendingResponse,
    PaymentReceivedResponse,
    PaymentRefusedResponse,
    PaymentUnknownResponse,
)
from amuse.vendor.adyen.helpers import (
    convert_to_end_of_the_day,
    get_adyen_client,
    get_or_create_payment_method,
)
from payments.models import PaymentTransaction
from subscriptions.models import (
    Subscription,
    SubscriptionPlanChanges,
    IntroductoryPriceCard,
)

logger = logging.getLogger(__name__)


class AdyenBase:
    """
    Provides private helper methods
    """

    response_code_exception_mapping = {
        "Cancelled": PaymentCancelledResponse,
        "Declined": PaymentRefusedResponse,
        "Error": PaymentErrorResponse,
        "Pending": PaymentPendingResponse,
        "Received": PaymentReceivedResponse,
        'ChallengeShopper': PaymentActionResponse,
        "RedirectShopper": PaymentActionResponse,
        "IdentifyShopper": PaymentActionResponse,
        "Refused": PaymentRefusedResponse,
    }

    def __init__(self):
        self.client = get_adyen_client()

    def _get_endpoint_callable(self):
        raise NotImplementedError()

    def _checkout(self, payload, payment, subscription_status, renewal=False):
        endpoint_callable = self._get_endpoint_callable()
        try:
            logger.info(f'Calling Adyen endpoint with: {payload}')
            payment_response = endpoint_callable(payload).message
            logger.info(f'Adyen response: {payment_response}')
            self._handle_checkout_response(
                payment_response, payment, subscription_status, renewal
            )
        except AdyenAPIResponseError as e:
            if payment.subscription:
                payment.subscription.status = Subscription.STATUS_ERROR
                payment.subscription.save()
            raise CheckoutError(payment, e)

    def _handle_checkout_response(
        self, response, payment, subscription_status, renewal=False
    ):
        """Payment flow completed. For list of result codes refer to:
        https://docs.adyen.com/checkout/payment-result-codes
        """
        # TODO: figure out how to handle different result codes, notify user in some cases?
        payment.external_payment_response = response
        result_code = response["resultCode"]
        logger.info(f'Received Adyen response: {result_code} with data: {response}')

        if result_code in (
            'RedirectShopper',
            'IdentifyShopper',
            'ChallengeShopper',
            'Pending',
        ):
            payment.customer_payment_payload = response.get("paymentData")
            payment.save()
        else:
            payment.external_transaction_id = response["pspReference"]

        if result_code in ["Authorised", "Received"]:
            payment_method = get_or_create_payment_method(payment.user, response)
            if renewal:
                sub = payment.subscription
                payment_method = sub.payment_method

            if hasattr(self, 'subscription_plan'):
                payment.subscription.plan = self.subscription_plan
                payment.plan = self.subscription_plan
            else:
                # This happens if a user re-activates subscription and 3DS is required,
                # when 3DS flow is completed the selected plan should be set to current
                payment.subscription.plan = payment.plan
            plan_changes = SubscriptionPlanChanges.objects.filter(
                subscription=payment.subscription, valid=True
            )
            if plan_changes and payment.type == PaymentTransaction.TYPE_PAYMENT:
                payment.subscription.plan = plan_changes.last().new_plan
                plan_changes.update(completed=True, valid=False)

            # before we enable the new subscription, expire any existing active
            # subscriptions this user has - this is necessary to ensure data consistency
            # in case of tier upgrade but also nice-to-do in general case, if there's a
            # data mismatch
            for stale_subscription in payment.user.subscriptions.active().exclude(
                pk=payment.subscription.pk
            ):
                stale_subscription.status = Subscription.STATUS_EXPIRED
                stale_subscription.valid_until = timezone.now().date()
                stale_subscription.save()
                last_payment = stale_subscription.latest_payment()
                last_payment.paid_until = timezone.now().date()
                last_payment.save()
                logger.info(
                    f'Expired (stale) active Subscription {stale_subscription.pk} for User {payment.user.pk}'
                )

            # and now we can enable the new subscription
            payment.subscription.payment_method = payment_method
            payment.subscription.status = subscription_status
            payment.subscription.valid_until = None
            payment.subscription.save()

            payment.payment_method = payment_method
            payment.status = PaymentTransaction.STATUS_APPROVED
            payment.save()
        else:
            raise self.response_code_exception_mapping.get(
                result_code, PaymentUnknownResponse
            )(result_code, payment, response)

    def _get_base_payload(self, payment):
        notification_url = settings.APP_URL.rstrip("/") + reverse("adyen-notifications")
        payload = {
            "accountInfo": {
                "accountCreationDate": self.user.created.isoformat(),
                "purchasesLast6Months": self.user.paymenttransaction_set.filter(
                    created__gt=timezone.now() - relativedelta(months=6),
                    status=PaymentTransaction.STATUS_APPROVED,
                ).count(),
                "pastTransactionsYear": self.user.paymenttransaction_set.filter(
                    created__gt=timezone.now() - relativedelta(months=12),
                    status=PaymentTransaction.STATUS_APPROVED,
                ).count(),
            },
            "reference": str(payment.pk),
            "shopperEmail": self.user.email,
            "recurringProcessingModel": "Subscription",
            "merchantAccount": settings.ADYEN_MERCHANT_ACCOUNT,
            "notificationUrl": notification_url,
        }
        if self.custom_price:
            price = self.custom_price['amount']
            currency = self.custom_price['currency']
            payload["amount"] = {
                "value": int(price * pow(10, currency.decimals)),
                "currency": currency.code,
            }
        elif self.localised:
            price_card = self.subscription_plan.get_price_card(
                self.country.code, self.is_introductory_price
            )
            payload["amount"] = {
                "value": price_card.price_adyen,
                "currency": price_card.currency.code,
            }
        else:
            payload["amount"] = {
                "value": self.subscription_plan.get_price_card().price_adyen,
                "currency": self.subscription_plan.get_price_card().currency.code,
            }
        try:
            phone = format_phonenumber(self.user.phone, self.user.country)
            payload['accountInfo']['mobilePhone'] = phone
        except (FakePhoneNumberError, InvalidPhoneNumberError):
            pass
        if self.country:
            payload['countryCode'] = self.country.code

        return payload

    def _get_new_payload(self, payment, is_3d_secure=False):
        payload = self._get_base_payload(payment)
        payload.update(
            {
                "shopperIP": self.ip,
                "channel": self.channel,
                "paymentMethod": self.payment_details,
                "returnUrl": self.return_url or self._get_default_return_url(payment),
                "shopperInteraction": "Ecommerce",
                "shopperReference": str(self.user.pk),
                "storePaymentMethod": True,
            }
        )
        if self.billing_address:
            payload["billingAddress"] = self.billing_address
        if self.channel == "Web" and self.browser_info:
            payload["origin"] = settings.WRB_URL
            payload["browserInfo"] = self.browser_info
        if is_3d_secure:
            payload = self._add_3ds_payload(payload, payment)
        return payload

    def _get_renew_payload(self, payment):
        payload = self._get_base_payload(payment)
        method = payment.subscription.payment_method.method
        payload.update(
            {
                "paymentMethod": {
                    "type": method == "paypal" and "paypal" or "scheme",
                    "storedPaymentMethodId": payment.subscription.payment_method.external_recurring_id,
                },
                "shopperInteraction": "ContAuth",
                "shopperReference": str(payment.user_id),
                "returnUrl": self.return_url or settings.WRB_URL,
            }
        )
        return payload

    def _get_authorise_payload(self, payment_details, payment, is_3d_secure=False):
        reference = "%s-AUTH-%s" % (self.user.pk, timezone.now().isoformat())
        payload = {
            "channel": self.channel,
            "paymentMethod": payment_details,
            "shopperEmail": self.user.email,
            "shopperIP": self.ip,
            "storePaymentMethod": True,
            "reference": reference,
            "shopperInteraction": "Ecommerce",
            "shopperReference": str(self.user.pk),
            "merchantAccount": settings.ADYEN_MERCHANT_ACCOUNT,
            "returnUrl": self.return_url or self._get_default_return_url(payment),
        }
        if self.billing_address:
            payload["billingAddress"] = self.billing_address
        if self.localised:
            price_card = self.subscription_plan.get_price_card(self.country.code)
            payload["amount"] = {"value": 0, "currency": price_card.currency.code}
        else:
            payload["amount"] = {
                "value": 0,
                "currency": payment.plan.get_price_card().currency.code,
            }
        if self.channel == "Web":
            payload["origin"] = settings.WRB_URL
            payload["browserInfo"] = self.browser_info
        if is_3d_secure:
            payload = self._add_3ds_payload(payload, payment)
        return payload

    def _add_3ds_payload(self, payload, payment):
        payload["additionalData"] = {"allow3DS2": True, "executeThreeD": True}
        payload.update(self._3d_secure_extra_data())
        payload["returnUrl"] = self.return_url or self._get_default_return_url(payment)
        return payload

    def _3d_secure_extra_data(self):
        """Additional fields required when performing 3DS payments, see:
        https://docs.adyen.com/checkout/3d-secure/api-reference#3d-secure-2-additional-parameters
        """
        data = {
            # TODO: strongly recommended by Adyen, not currently stored in DB
            # 'billingAddress': {},
            "merchantRiskIndicator": {
                "deliveryAddressIndicator": "digitalGoods",
                "deliveryEmail": self.user.email,
                "deliveryTimeframe": "electronicDelivery",
                "reorderItems": self.user.paymenttransaction_set.filter(
                    subscription__plan=self.subscription_plan.pk,
                    status=PaymentTransaction.STATUS_APPROVED,
                ).exists(),
            }
        }
        return data

    def _get_default_return_url(self, payment):
        encrypted_user_id = TimestampSigner().sign(payment.user.pk)
        return settings.APP_URL.rstrip("/") + reverse(
            "adyen_3ds",
            kwargs={"payment_id": payment.pk, "encrypted_user_id": encrypted_user_id},
        )


class AdyenSubscription(AdyenBase):
    """
    Provides the actual developer interface for interacting with Adyen

    Optional kwargs are only used for new subscriptions and when authorising
    new payment method, not for renewals/cancellations.
    """

    def __init__(
        self,
        user,
        subscription_plan=None,
        payment_details=None,
        country=None,
        client=None,
        ip=None,
        browser_info=None,
        force_3ds=False,
        return_url=None,
        localised=False,
        billing_address=None,
        custom_price=None,
        is_introductory_price=False,
    ):
        super().__init__()
        self.user = user
        self.subscription_plan = subscription_plan
        self.payment_details = payment_details
        self.country = country
        self.channel = "Android" if client == CLIENT_ANDROID else "Web"
        self.ip = ip
        self.browser_info = browser_info
        self.force_3ds = force_3ds
        self.return_url = return_url
        self.localised = localised
        self.billing_address = billing_address
        self.custom_price = custom_price
        self.is_introductory_price = is_introductory_price

    def _get_endpoint_callable(self):
        return self.client.checkout.payments

    def _get_platform(self):
        "self.channel can be either 'Android' or 'Web'"
        if self.channel == "Android":
            return PaymentTransaction.PLATFORM_ANDROID

        if self.channel == "Web":
            return PaymentTransaction.PLATFORM_WEB

        return PaymentTransaction.PLATFORM_UNKNOWN

    def authorise_payment_method(self):
        subscription = self.user.current_subscription()

        card = (
            self.subscription_plan.get_price_card(
                self.country.code, use_intro_price=self.is_introductory_price
            )
            if self.localised
            else self.subscription_plan.get_price_card(
                use_intro_price=self.is_introductory_price
            )
        )
        currency = card.currency
        platform = self._get_platform()

        paid_until = convert_to_end_of_the_day(subscription.paid_until)
        zero_amount_payment = PaymentTransaction.objects.create(
            amount=0,
            country=self.country,
            type=PaymentTransaction.TYPE_AUTHORISATION,
            paid_until=paid_until,
            payment_method=subscription.payment_method,
            plan=subscription.plan,
            subscription=subscription,
            user=self.user,
            vat_amount=0,
            vat_amount_sek=0,
            vat_percentage=self.country.vat_percentage,
            currency=currency,
            platform=platform,
        )
        payload = self._get_authorise_payload(
            self.payment_details, zero_amount_payment, is_3d_secure=self.force_3ds
        )
        self._checkout(payload, zero_amount_payment, Subscription.STATUS_ACTIVE)

    def authorise_payment_method_3ds(self, zero_amount_payment):
        payload = self._get_authorise_payload(
            self.payment_details, zero_amount_payment, is_3d_secure=True
        )
        self._checkout(payload, zero_amount_payment, Subscription.STATUS_ACTIVE)

    def create(self):
        now = timezone.now()
        today = now.date()

        subscription = Subscription.objects.create(
            plan=self.subscription_plan,
            provider=Subscription.PROVIDER_ADYEN,
            user=self.user,
            valid_from=today,
        )

        duration_months = self.subscription_plan.period
        if self.custom_price:
            amount = self.custom_price['amount']
            currency = self.custom_price['currency']
        else:
            card = (
                self.subscription_plan.get_price_card(
                    self.country.code, use_intro_price=self.is_introductory_price
                )
                if self.localised
                else self.subscription_plan.get_price_card(
                    use_intro_price=self.is_introductory_price
                )
            )
            amount = card.price
            currency = card.currency
            duration_months = (
                card.period
                if isinstance(card, IntroductoryPriceCard)
                else duration_months
            )

        platform = self._get_platform()
        payment_type = (
            PaymentTransaction.TYPE_PAYMENT
            if self.is_introductory_price == False
            else PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT
        )
        vat_amount, vat_amount_sek = calculate_vat(self.country, currency.code, amount)

        new_payment = PaymentTransaction.objects.create(
            amount=amount,
            country=self.country,
            type=payment_type,
            paid_until=now + relativedelta(months=duration_months),
            payment_method=subscription.payment_method,
            plan=subscription.plan,
            subscription=subscription,
            user=self.user,
            vat_amount=vat_amount,
            vat_amount_sek=vat_amount_sek,
            vat_percentage=self.country.vat_percentage,
            currency=currency,
            platform=platform,
            category=PaymentTransaction.CATEGORY_INITIAL,
        )

        payload = self._get_new_payload(new_payment, self.force_3ds)

        self._checkout(payload, new_payment, Subscription.STATUS_ACTIVE)

    def create_3ds(self, payment):
        payload = self._get_new_payload(payment, is_3d_secure=True)
        self._checkout(payload, payment, Subscription.STATUS_ACTIVE)

    def renew(self, subscription):
        latest_payment = subscription.latest_payment()
        country = latest_payment.country
        currency = latest_payment.currency
        plan = subscription.plan

        # get new plan from SubscriptionPlanChanges if exit
        last_plan_change = subscription.plan_changes.filter(
            valid=True, completed=False
        ).last()

        if last_plan_change:
            plan = last_plan_change.new_plan
            logger.info(
                f"Renew with plan change current{subscription.plan.name} -> new{plan.name}"
            )

        # if there's no PriceCard for the currency, default to USD
        if not plan.pricecard_set.filter(currency=currency).exists():
            price_card = subscription.plan.get_price_card(country)
            currency = price_card.currency
            logger.info(
                f"Renew unable to find local currency for sub={subscription.pk} fallback to {currency.name}"
            )

        paid_until = convert_to_end_of_the_day(
            latest_payment.paid_until
        ) + relativedelta(months=plan.period)
        if self.localised:
            amount = plan.get_price_card(country.code).price
        else:
            amount = plan.get_price_card().price

        vat_amount, vat_amount_sek = calculate_vat(country, currency.code, amount)
        new_payment = PaymentTransaction.objects.create(
            amount=amount,
            country=country,
            type=PaymentTransaction.TYPE_PAYMENT,
            paid_until=paid_until,
            payment_method=subscription.payment_method,
            plan=plan,
            subscription=subscription,
            user=self.user,
            vat_amount=vat_amount,
            vat_amount_sek=vat_amount_sek,
            vat_percentage=country.vat_percentage,
            currency=currency,
            platform=PaymentTransaction.PLATFORM_CRON,
            category=PaymentTransaction.CATEGORY_RENEWAL,
        )
        self.subscription_plan = plan
        self.country = country

        payload = self._get_renew_payload(new_payment)
        self._checkout(payload, new_payment, Subscription.STATUS_ACTIVE, True)

    def upgrade_tier(self, current_subscription, new_plan):
        latest_payment = current_subscription.latest_payment()
        country = latest_payment.country
        currency = latest_payment.currency

        now = timezone.now()
        today = now.date()

        new_subscription = Subscription.objects.create(
            plan=new_plan,
            provider=Subscription.PROVIDER_ADYEN,
            user=self.user,
            valid_from=today,
            payment_method=current_subscription.payment_method,
        )

        # per the business rules agreed, we start a new Subscription from the point
        # User upgrades to new Tier, which is why we use datetime.now as start time
        paid_until = convert_to_end_of_the_day(now) + relativedelta(
            months=new_plan.period
        )

        vat_amount, vat_amount_sek = calculate_vat(
            country, currency.code, self.custom_price['amount']
        )
        new_payment = PaymentTransaction.objects.create(
            amount=self.custom_price['amount'],
            country=country,
            type=PaymentTransaction.TYPE_PAYMENT,
            paid_until=paid_until,
            payment_method=current_subscription.payment_method,
            plan=new_plan,
            subscription=new_subscription,
            user=self.user,
            vat_amount=vat_amount,
            vat_amount_sek=vat_amount_sek,
            vat_percentage=country.vat_percentage,
            currency=currency,
            platform=PaymentTransaction.PLATFORM_WEB,
            category=PaymentTransaction.CATEGORY_INITIAL,
        )
        self.subscription_plan = new_plan
        self.country = country

        payload = self._get_renew_payload(new_payment)
        self._checkout(payload, new_payment, Subscription.STATUS_ACTIVE)


class Adyen3DS(AdyenBase):
    def _get_endpoint_callable(self):
        return self.client.checkout.payments_details

    def authorise_3ds(self, data, payment):
        payload = {"paymentData": payment.customer_payment_payload, "details": data}
        self._checkout(payload, payment, Subscription.STATUS_ACTIVE)


class AdyenRefund(AdyenBase):
    def __init__(self, payment):
        super().__init__()
        self.payment = payment

    def _get_refund_payload(self):
        data = {
            "merchantAccount": settings.ADYEN_MERCHANT_ACCOUNT,
            "modificationAmount": {
                "value": self.payment.get_amount_formatted_adyen,
                "currency": self.payment.currency.code,
            },
            "originalReference": self.payment.external_transaction_id,
            "reference": self.payment.pk,
        }
        return data

    def refund(self):
        try:
            response = self.client.payment.refund(self._get_refund_payload())
            return {"is_success": True, "response": response.message}
        except Exception as e:
            logger.error(
                f'Error executing Adyen refund for payment_id {self.payment.pk} error={e}'
            )
            return {"is_success": False, "response": e}


class AdyenGetRecurringInfo(AdyenBase):
    def __init__(self):
        super().__init__()

    def get_recurring_info(self, user_id):
        data = {
            "merchantAccount": settings.ADYEN_MERCHANT_ACCOUNT,
            "shopperReference": user_id,
        }
        try:
            response = self.client.recurring.list_recurring_details(data)
            return response.message
        except Exception as e:
            logger.warning(f'Error while getting recurring info error={e}')
