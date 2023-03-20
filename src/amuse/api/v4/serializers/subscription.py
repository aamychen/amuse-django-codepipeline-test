import logging
from datetime import timedelta
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from amuse.analytics import subscription_new_started
from amuse.api.base.views.exceptions import Adyen3DSRequiredError, AppleServerError
from amuse.api.v4.serializers.subscription_plan import SubscriptionPlanSerializer
from amuse.platform import PlatformType
from amuse.utils import get_ip_address, parse_client_version
from amuse.vendor.adyen import (
    authorise_payment_method,
    create_subscription,
    get_payment_country,
)
from amuse.vendor.adyen.exceptions import IssuerCountryAPIError
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
from subscriptions.models import Subscription, SubscriptionPlan, SubscriptionPlanChanges
from users.models import UserMetadata


logger = logging.getLogger(__name__)
apple_subscription_logger = logging.getLogger('apple.subscription')


class BaseSubscriptionSerializer(serializers.Serializer):
    country = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.filter(is_adyen_enabled=True), many=False
    )
    payment_details = serializers.DictField()
    return_url = serializers.CharField(max_length=1024, required=False)

    def validate(self, data):
        # Validate payment country
        request = self.context['request']
        country = data['country']
        payment_country = None

        # disable country lookup for paypal since no country data is available
        payment_method = data['payment_details']['paymentMethod']['type']
        if payment_method != 'paypal':
            try:
                payment_country = get_payment_country(
                    request.user.pk, data['payment_details']
                )
            except IssuerCountryAPIError:
                raise serializers.ValidationError(
                    {'country': 'Payment country lookup failed'}
                )
            # for some reason Adyen Client APIs (especially Android) don't send this
            # info reliably so catch the eventual errors just in case
            except (KeyError, IndexError, ValueError) as err:
                logger.warning(
                    f'Unable to fetch payment country for data: {data}, err: {err}'
                )

        if payment_country is None:
            logger.info(
                'Country lookup failed, setting to %s for user_id %s',
                data['country'],
                request.user.pk,
            )
        elif payment_country != country:
            raise serializers.ValidationError(
                {
                    'country': 'Card is from different country than you selected. '
                    'You selected %s and the card is from %s. Please change payment '
                    'country or use a card from your selected country.'
                    % (country.name, payment_country.name)
                }
            )

        # TODO: Enable this once majority of Android users have updated to >= v3.7
        # # billingAddress is mandatory for US/UK/CA
        # if country.code in ['US', 'UK', 'CA']:
        #     payment_details = data['payment_details']
        #     if not payment_details.get('billingAddress'):
        #         raise serializers.ValidationError(
        #             {'payment_details': 'Please specify a billing address'}
        #         )

        return data

    def validate_return_url(self, value):
        '''Ensure either app-specific URL or Amuse controlled domain URL'''
        if len(value) > 0:
            is_allowed_android = value.startswith('adyencheckout://io.amuse')
            host = urlparse(value).hostname
            is_allowed_web_url = host and host.endswith('amuse.io')
            if not (is_allowed_android or is_allowed_web_url):
                raise serializers.ValidationError('Invalid return_url')
        return value


class SubscriptionSerializer(BaseSubscriptionSerializer):
    plan = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.filter(is_public=True), many=False
    )

    def save(self, is_reactivate=False):
        request = self.context['request']
        subscription_plan = self.validated_data['plan']
        payment_details = self.validated_data['payment_details']
        country = self.validated_data['country']
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
            )
        else:
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
            )
        if not response['is_success']:
            # In case of 3DS payment a further action is required.
            raise Adyen3DSRequiredError(adyen_response=response)
        return response


class UpdateSubscriptionPaymentMethodSerializer(BaseSubscriptionSerializer):
    pass


class ChangeSubscriptionSerializer(serializers.Serializer):
    plan = serializers.PrimaryKeyRelatedField(
        many=False, queryset=SubscriptionPlan.objects.filter(is_public=True)
    )

    def is_plan_change_allowed(self, plan, user):
        '''Temporary block plan change form PLUS to PRO'''
        if (
            user.tier == SubscriptionPlan.TIER_PLUS
            and plan.tier == SubscriptionPlan.TIER_PRO
        ):
            raise serializers.ValidationError(
                {'plan': 'Plan change from TIER_PLUS to TIER_PRO not implemented.'}
            )

    def _downgrade_from_pro_to_plus_case(self, plan, user, subscription):
        """Temporary solution for PRO->PLUS downgrade
        Renew cron job will execute downgrade once original SUB expire.
        """
        if (
            user.tier == SubscriptionPlan.TIER_PRO
            and plan.tier == SubscriptionPlan.TIER_PLUS
        ):
            if subscription.plan_changes.filter(valid=True).count() >= 1:
                raise serializers.ValidationError(
                    {'plan': 'Plan change for this subscription exist.'}
                )

            # create record in SubscriptionPlanChanges
            SubscriptionPlanChanges.objects.create(
                subscription=subscription, current_plan=subscription.plan, new_plan=plan
            )
            return subscription

    def update(self, subscription, validated_data):
        plan = validated_data['plan']
        user = subscription.user
        self.is_plan_change_allowed(plan, user)
        downgraded_sub = self._downgrade_from_pro_to_plus_case(plan, user, subscription)
        if downgraded_sub:
            return downgraded_sub
        subscription.plan = plan
        subscription.save()

        return subscription


class CurrentSubscriptionSerializer(serializers.ModelSerializer):
    payment_expiry_date = serializers.CharField(source='payment_method_expiry_date')
    payment_method = serializers.CharField(source='payment_method_method')
    payment_summary = serializers.CharField(source='payment_method_summary')
    current_plan = SubscriptionPlanSerializer(source='get_current_plan')
    plan = SubscriptionPlanSerializer(source='get_next_plan')
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


class AdyenPaymentMethodsSerializer(serializers.Serializer):
    country = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.filter(is_adyen_enabled=True), many=False
    )
    subscription_plan = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.filter(is_public=True), many=False
    )


class AppleSubscriptionSerializer(serializers.Serializer):
    receipt_data = serializers.CharField()

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

    def save(self, **kwargs):
        request = self.context['request']
        user = request.user
        original_transaction_id = self.validated_data['original_transaction_id']

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
            valid_from=timezone.now().date(),
        )
        country = None
        if user.country:
            country = Country.objects.filter(code=user.country.upper()).first()
        if country is None:
            country = Country.objects.get(code='SE')

        paid_until = self.validated_data['expires_date']
        card = plan.get_price_card()
        create_apple_payment(
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
            type=PaymentTransaction.TYPE_PAYMENT,
            user=user,
            vat_amount=country.vat_amount(card.price),
            vat_percentage=country.vat_percentage,
            currency=card.currency,
            platform=PaymentTransaction.PLATFORM_IOS,
        )

        ip = get_ip_address(request)
        client = request.META.get('HTTP_USER_AGENT', '')

        subscription_new_started(subscription, PlatformType.IOS, client, ip)

        apple_subscription_logger.info(
            'Apple subscription was created successfully',
            extra={
                'subscription_id': subscription.pk,
                'user_id': user.pk,
                'original_transaction_id': original_transaction_id,
            },
        )
