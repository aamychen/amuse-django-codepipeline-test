from decimal import Decimal
from typing import Optional
from countries.models import Country, Currency
from payments.models import PaymentTransaction, PaymentMethod, SubscriptionPlan
from subscriptions.models import Subscription
from subscriptions.rules import ChangeReason, Action
from subscriptions.vendor.google.purchase_subscription import (
    PurchaseSubscription as GoogleSubscription,
    PurchaseSubscription,
)
from users.models import User
from .. import GooglePlayAPI
from ..enums import PaymentState, AcknowledgementState
from ..errors import (
    SubscriptionPlanNotFoundError,
    InvalidPurchaseTokenError,
    UserNotEligibleForFreeTrial,
    PurchaseTokenAlreadyUsedError,
)
from ..helpers import info, payment_state_2_payment_transaction_status


class SubscriptionCreatorArgs(object):
    def __init__(
        self,
        purchase_token: str,
        google_subscription_id: str,
        purchase: PurchaseSubscription,
        plan: SubscriptionPlan,
        change_reason: ChangeReason,
        is_renewal: bool,
        is_upgrade: bool,
        customer_payload: Optional[dict],
    ):
        self.purchase_token = purchase_token
        self.google_subscription_id = google_subscription_id
        self.purchase = purchase
        self.plan = plan
        self.change_reason = change_reason
        self.is_renewal = is_renewal
        self.is_upgrade = is_upgrade
        self.customer_payload = customer_payload


class ChargedPrice(object):
    def __init__(
        self,
        purchase: GoogleSubscription,
        payment_type: PaymentTransaction.TYPE_CHOICES,
        is_in_introductory_price_period: bool,
        is_upgrade: bool,
    ):
        self.purchase = purchase
        self.payment_type = payment_type
        self.is_in_introductory_price_period = is_in_introductory_price_period
        self.is_upgrade = is_upgrade

    @property
    def amount(self):
        if self.is_in_introductory_price_period:
            return self.purchase.introductory_price_info.price_amount

        if self.payment_type == PaymentTransaction.TYPE_FREE_TRIAL:
            return Decimal('0.0')

        if self.is_upgrade is True:
            # amuse use IMMEDIATE_WITH_TIME_PRORATION for upgrade. In this mode, time
            # is prorated; amount is not prorated. Amount is 0.0 always. If we change
            # the proration mode (on client side), we would need to change this this
            # if-statement will not
            return Decimal('0.0')

        return self.purchase.price_amount

    @property
    def currency_code(self):
        if self.is_in_introductory_price_period:
            return self.purchase.introductory_price_info.price_currency_code

        return self.purchase.price_currency_code


class SubscriptionCreator:
    def create_from_admin(
        self, event_id: str, user: User, google_product_id: str, purchase_token: str
    ):
        plan = self._get_subscription_plan(google_product_id)

        purchase = self._get_subscription_purchase(
            event_id, google_product_id, purchase_token
        )

        params = SubscriptionCreatorArgs(
            purchase_token=purchase_token,
            google_subscription_id=google_product_id,
            purchase=purchase,
            plan=plan,
            change_reason=ChangeReason.GOOGLE_ADMIN_NEW,
            is_renewal=False,
            is_upgrade=False,
            customer_payload={
                'google_product_id': google_product_id,
                'purchase_token': purchase_token,
                'user_id': user.id,
            },
        )

        return self._create_subscription(event_id, user, params)

    def create_from_purchase_notification(
        self,
        event_id: str,
        user: User,
        validated_data: dict,
        purchase: PurchaseSubscription,
    ):
        google_subscription_id = validated_data['google_subscription_id']
        purchase_token = validated_data['purchase_token']

        plan = self._get_subscription_plan(google_subscription_id)

        params = SubscriptionCreatorArgs(
            purchase_token=purchase_token,
            google_subscription_id=google_subscription_id,
            purchase=purchase,
            plan=plan,
            change_reason=ChangeReason.GOOGLE_PURCHASED,
            is_renewal=False,
            is_upgrade=False,
            customer_payload=validated_data,
        )

        return self._create_subscription(event_id, user, params)

    def create_from_user_endpoint(
        self,
        event_id: str,
        user: User,
        validated_data: dict,
        purchase: PurchaseSubscription,
    ):
        google_subscription_id = validated_data['google_subscription_id']
        purchase_token = validated_data['purchase_token']

        self._validate_purchase_token(purchase_token)

        plan = self._get_subscription_plan(google_subscription_id)
        self._validate_free_trial_eligibility(plan, user, google_subscription_id)

        params = SubscriptionCreatorArgs(
            purchase_token=purchase_token,
            google_subscription_id=google_subscription_id,
            purchase=purchase,
            plan=plan,
            change_reason=ChangeReason.GOOGLE_NEW,
            is_renewal=False,
            is_upgrade=False,
            customer_payload=validated_data,
        )

        return self._create_subscription(event_id, user, params)

    def create_from_google_webhook(
        self, event_id: str, user: User, params: SubscriptionCreatorArgs
    ):
        return self._create_subscription(event_id, user, params)

    def _create_subscription(
        self, event_id: str, user: User, params: SubscriptionCreatorArgs
    ):
        # Gather data
        purchase = params.purchase
        plan = params.plan
        valid_until = None if purchase.auto_renewing else purchase.expiry_date
        status = self._get_payment_transaction_status(purchase)
        payment_category = (
            PaymentTransaction.CATEGORY_RENEWAL
            if params.is_renewal
            else PaymentTransaction.CATEGORY_INITIAL
        )
        is_introductory_price = self._is_in_introductory_price_period(
            purchase, payment_category
        )
        payment_type = self._get_payment_type(purchase, is_introductory_price)
        charged_price = ChargedPrice(
            purchase, payment_type, is_introductory_price, params.is_upgrade
        )
        free_trial_from = self._get_free_trial_from(purchase, payment_type)
        free_trial_until = self._get_free_trial_until(purchase, payment_type)

        country = Country.objects.filter(code=purchase.country_code.upper()).first()
        currency = Currency.objects.filter(
            code=charged_price.currency_code.upper()
        ).first()

        # Everything OK. Create PaymentMethod, Subscription, and Transaction.
        payment_method = PaymentMethod.objects.create(
            external_recurring_id=params.purchase_token, method='GOOGL', user=user
        )
        subscription = Action.create(
            payment_method,
            plan,
            Subscription.PROVIDER_GOOGLE,
            params.change_reason,
            free_trial_from,
            free_trial_until,
            valid_until,
        )

        payment = PaymentTransaction.objects.create(
            amount=charged_price.amount,
            category=payment_category,
            country=country,
            customer_payment_payload=params.customer_payload,
            external_payment_response=purchase.payload,
            external_transaction_id=purchase.order_id,
            paid_until=purchase.expiry_date,
            payment_method=payment_method,
            plan=plan,
            status=status,
            subscription=subscription,
            type=payment_type,
            user=user,
            vat_amount=0,
            vat_percentage=0,
            currency=currency,
            platform=PaymentTransaction.PLATFORM_ANDROID,
        )
        info(event_id, f'PaymentTransaction created, id={payment.id}')

        info(
            event_id,
            f'Created new subscription={subscription.id}, transaction={payment.id}, method={payment_method.id}',
        )
        return subscription

    def _get_payment_transaction_status(self, purchase):
        status = payment_state_2_payment_transaction_status(purchase.payment_state)
        if status:
            return status

        if purchase.acknowledgement_state == AcknowledgementState.ACKNOWLEDGED:
            return PaymentTransaction.STATUS_APPROVED

        return PaymentTransaction.STATUS_PENDING

    @staticmethod
    def _get_payment_type(purchase: GoogleSubscription, is_introductory_price: bool):
        if purchase.payment_state == PaymentState.FREE_TRIAL:
            return PaymentTransaction.TYPE_FREE_TRIAL

        if is_introductory_price:
            return PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT

        return PaymentTransaction.TYPE_PAYMENT

    @staticmethod
    def _get_free_trial_from(
        purchase: GoogleSubscription, payment_type: PaymentTransaction.STATUS_CHOICES
    ):
        if purchase.payment_state == PaymentState.FREE_TRIAL:
            return purchase.start

        return None

    @staticmethod
    def _get_free_trial_until(
        purchase: GoogleSubscription, payment_type: PaymentTransaction.STATUS_CHOICES
    ):
        if purchase.payment_state == PaymentState.FREE_TRIAL:
            return purchase.expiry_date

        return None

    @staticmethod
    def _get_subscription_plan(google_product_id: str):
        plan = SubscriptionPlan.objects.get_by_google_product_id(google_product_id)
        if plan is None:
            raise SubscriptionPlanNotFoundError(google_product_id)
        return plan

    @staticmethod
    def _get_subscription_purchase(
        request_id: str, google_subscription_id: str, purchase_token: str
    ):
        api = GooglePlayAPI()
        purchase = api.verify_purchase_token(
            request_id, google_subscription_id, purchase_token
        )
        if purchase is None:
            raise InvalidPurchaseTokenError(google_subscription_id, purchase_token)

        return GoogleSubscription(**purchase)

    @staticmethod
    def _is_in_introductory_price_period(
        purchase: GoogleSubscription,
        payment_category: PaymentTransaction.CATEGORY_CHOICES,
    ):
        """
        Google purchase payload does not contain a field that explicitly indicates the
        subscription is currently in the introductory price period.

        NOTE: Google supports multiple introductory price periods (IPP) - this method
        will recognize only the first IPP.
        """
        if purchase.introductory_price_info is None:
            # If the subscription contains the the introductory_price_info field, then
            # it is MAYBE in the IPP, otherwise we are sure IT IS NOT in the IPP.
            return False

        if payment_category == PaymentTransaction.CATEGORY_INITIAL:
            # If the subscription contains introductory_price_info field and it is the
            # first billing period, then the subscription is PROBABLY in the IPP.
            return True

        return False

    @staticmethod
    def _validate_free_trial_eligibility(
        plan: SubscriptionPlan, user: User, google_product_id: str
    ):
        is_free_trial_plan = google_product_id == plan.google_product_id
        if not is_free_trial_plan:
            return plan

        if not user.is_free_trial_eligible():
            raise UserNotEligibleForFreeTrial(user.id)

        return plan

    @staticmethod
    def _validate_purchase_token(purchase_token: str):
        if PaymentMethod.objects.filter(external_recurring_id=purchase_token).exists():
            raise PurchaseTokenAlreadyUsedError()
