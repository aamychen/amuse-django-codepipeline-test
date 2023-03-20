import logging
from uuid import uuid4

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from amuse.analytics import subscription_new_intro_started, subscription_new_started
from amuse.api.base.views.exceptions import Adyen3DSRequiredError, AppleServerError
from amuse.api.v4.serializers.subscription import (
    SubscriptionSerializer as SubscriptionV4Serializer,
)
from amuse.api.v5.serializers.subscription_plan import CurrentSubscriptionPlanSerializer
from amuse.platform import PlatformType
from amuse.utils import get_ip_address, parse_client_version
from amuse.vendor.adyen import authorise_payment_method, create_subscription
from amuse.vendor.apple.exceptions import (
    DuplicateAppleSubscriptionError,
    DuplicateAppleTransactionIDError,
    EmptyAppleReceiptError,
    MaxRetriesExceededError,
    UnknownAppleError,
)
from amuse.vendor.apple.subscriptions import AppleReceiptValidationAPIClient
from countries.models import Country
from payments.helpers import create_apple_payment
from payments.models import PaymentMethod, PaymentTransaction
from subscriptions.models import Subscription, SubscriptionPlan
from users.models import UserMetadata

logger = logging.getLogger(__name__)
apple_subscription_logger = logging.getLogger('apple.subscription')


class CurrentSubscriptionSerializer(serializers.ModelSerializer):
    payment_expiry_date = serializers.CharField(source='payment_method_expiry_date')
    payment_method = serializers.CharField(source='payment_method_method')
    payment_summary = serializers.CharField(source='payment_method_summary')
    current_plan = CurrentSubscriptionPlanSerializer(source='get_current_plan')
    plan = CurrentSubscriptionPlanSerializer(source='get_next_plan')
    paid_until = serializers.DateField()

    class Meta:
        model = Subscription
        fields = (
            'current_plan',
            'paid_until',
            'payment_expiry_date',
            'payment_method',
            'payment_summary',
            'plan',
            'provider',
            'valid_from',
            'valid_until',
        )


class SubscriptionSerializer(SubscriptionV4Serializer):
    is_introductory_price = serializers.BooleanField(default=False, required=False)

    def check_introductory_price(
        self, is_introductory_price, country, subscription_plan
    ):
        if not is_introductory_price:
            return

        introductory_price_card = subscription_plan.get_introductory_price_card(
            country_code=country.code
        )

        if introductory_price_card is None:
            raise serializers.ValidationError(
                {'is_introductory_price': 'Introductory price is not available'}
            )

    def save(self, is_reactivate=False, custom_price=None):
        request = self.context['request']
        subscription_plan = self.validated_data['plan']
        payment_details = self.validated_data['payment_details']
        country = self.validated_data['country']
        is_introductory_price = self.validated_data['is_introductory_price']

        client = parse_client_version(request.META.get('HTTP_USER_AGENT', ''))[0]
        ip_address = get_ip_address(request)
        force_3ds = settings.ADYEN_PLATFORM == 'test'
        if is_reactivate:
            logger.info('Re-activating subscription for user_id: %s', request.user.pk)
            response = authorise_payment_method(
                user=request.user,
                payment_details=payment_details['paymentMethod'],
                country=country,
                client=client,
                ip=ip_address,
                browser_info=payment_details.get('browserInfo'),
                force_3ds=force_3ds,
                return_url=self.validated_data.get('return_url'),
                subscription_plan=subscription_plan,
                localised=True,
                billing_address=payment_details.get('billingAddress'),
            )
        else:
            self.check_introductory_price(
                is_introductory_price, country, subscription_plan
            )

            logger.info('Creating new subscription for user_id: %s', request.user.pk)
            response = create_subscription(
                user=request.user,
                subscription_plan=subscription_plan,
                payment_details=payment_details['paymentMethod'],
                country=country,
                client=client,
                ip=ip_address,
                browser_info=payment_details.get('browserInfo'),
                force_3ds=force_3ds,
                return_url=self.validated_data.get('return_url'),
                localised=True,
                billing_address=payment_details.get('billingAddress'),
                custom_price=custom_price,
                is_introductory_price=is_introductory_price,
            )
        if not response['is_success']:
            # In case of 3DS payment a further action is required.
            raise Adyen3DSRequiredError(adyen_response=response)
        return response


class AppleSubscriptionSerializer(serializers.Serializer):
    receipt_data = serializers.CharField()
    # apple/itunes store country
    country = serializers.CharField(
        min_length=2, max_length=2, allow_blank=False, allow_null=False, required=True
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context['request'].user
        request_id = str(uuid4())
        client = AppleReceiptValidationAPIClient(
            attrs['receipt_data'], request_id=request_id
        )

        # TODO this should be split up into several try/excepts.
        # TODO the helpers should not get the receipt every time.
        try:
            client.validate_receipt()
            attrs['original_transaction_id'] = client.get_original_transaction_id(user)
            attrs['transaction_id'] = client.get_transaction_id()
            attrs['product_id'] = client.get_product_id()
            attrs['expires_date'] = client.get_expires_date()
            attrs['purchase_date'] = client.get_purchase_date()
            attrs['restored_purchase'] = client.restored_purchase
            attrs['is_in_intro_offer_period'] = client.get_is_in_intro_offer()

        except (MaxRetriesExceededError, UnknownAppleError) as e:
            apple_server_error = AppleServerError()
            apple_server_error.default_detail = str(e)
            apple_subscription_logger.warning(
                'Apple server error',
                extra={
                    'user_id': user.pk,
                    'receipt_data': attrs,
                    'error': str(e),
                    'request_id': request_id,
                },
            )
            if attrs.get('receipt_data'):
                UserMetadata.objects.update_or_create(
                    user=user, apple_receipt=attrs['receipt_data']
                )

            raise apple_server_error
        except (
            DuplicateAppleTransactionIDError,
            DuplicateAppleSubscriptionError,
            EmptyAppleReceiptError,
        ) as e:
            apple_subscription_logger.warning(
                'Apple receipt validation error',
                extra={
                    'user_id': user.pk,
                    'receipt_data': attrs,
                    'error': str(e),
                    'request_id': request_id,
                },
            )
            raise serializers.ValidationError(str(e))

        apple_subscription_logger.info(
            'Apple receipt was validated successfully',
            extra={'user_id': user.pk, 'receipt_data': attrs, 'request_id': request_id},
        )

        return attrs

    def _get_country(self, user):
        # if apple receipt is valid, then country is probably valid
        # just in case of some shit-fuck, here is fallback for country
        # fallback code is copied from v4
        country_code = self.validated_data['country']
        country = Country.objects.filter(code=country_code.upper()).first()

        if country is None and user.country:
            logger.warning(
                "Country code %s is invalid. Instead, fallback value for user_id %s "
                "is used %s " % (country_code, user.pk, user.country)
            )
            country = Country.objects.filter(code=user.country.upper()).first()

        if country is None:
            logger.warning("Default country 'SE' is used for user_id %s" % (user.pk))
            country = Country.objects.get(code='SE')

        return country

    def save(self, **kwargs):
        request = self.context['request']
        user = request.user
        original_transaction_id = self.validated_data['original_transaction_id']
        is_restored_purchase = self.validated_data['restored_purchase']
        purchase_date = self.validated_data['purchase_date']

        country = self._get_country(user=user)

        payment_method = PaymentMethod.objects.create(
            external_recurring_id=original_transaction_id, method='AAPL', user=user
        )

        apple_product_id = self.validated_data['product_id']
        plan = SubscriptionPlan.objects.get_by_product_id(apple_product_id)

        if plan is None:
            apple_subscription_logger.warning(
                "SubscriptionPlan %s does not exist for user_id %s original_transaction_id %s"
                % (apple_product_id, user.pk, original_transaction_id)
            )
            raise serializers.ValidationError(
                f"SubscriptionPlan with apple_product id '{apple_product_id}' does not"
                " exist"
            )

        subscription = Subscription.objects.create(
            payment_method=payment_method,
            plan=plan,
            provider=Subscription.PROVIDER_IOS,
            status=Subscription.STATUS_ACTIVE,
            user=user,
            valid_from=purchase_date.date()
            if is_restored_purchase
            else timezone.now().date(),
        )

        paid_until = self.validated_data['expires_date']
        is_introductory_price = self.validated_data['is_in_intro_offer_period']

        payment_type = (
            PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT
            if is_introductory_price
            else PaymentTransaction.TYPE_PAYMENT
        )
        card = plan.get_price_card(
            country=country.code, use_intro_price=is_introductory_price
        )

        payment = create_apple_payment(
            amount=card.price,
            category=PaymentTransaction.CATEGORY_INITIAL,
            country=country,
            customer_payment_payload=self.data,
            external_transaction_id=self.validated_data['transaction_id'],
            paid_until=paid_until,
            payment_method=payment_method,
            plan=plan,
            status=PaymentTransaction.STATUS_APPROVED,
            subscription=subscription,
            type=payment_type,
            user=user,
            vat_amount=country.vat_amount(card.price),
            vat_percentage=country.vat_percentage,
            currency=card.currency,
            platform=PaymentTransaction.PLATFORM_IOS,
        )

        if payment is not None and is_restored_purchase:
            payment.created = purchase_date
            payment.save()

        ip = get_ip_address(request)
        client = request.META.get('HTTP_USER_AGENT', '')

        subscription_started = (
            subscription_new_intro_started
            if is_introductory_price
            else subscription_new_started
        )
        subscription_started(subscription, PlatformType.IOS, client, ip, country.code)
        apple_subscription_logger.info(
            'Apple subscription was created successfully',
            extra={
                'subscription_id': subscription.pk,
                'user_id': user.pk,
                'original_transaction_id': original_transaction_id,
            },
        )


class AppleSubscriptionInfoRequestSerializer(serializers.Serializer):
    receipt_data = serializers.CharField(required=True, allow_blank=False)


class CreateGoogleSubscriptionRequestSerializer(serializers.Serializer):
    purchase_token = serializers.CharField(required=True)
    google_subscription_id = serializers.CharField(required=True)
