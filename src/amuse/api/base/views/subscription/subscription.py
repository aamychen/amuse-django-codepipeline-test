import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.generics import CreateAPIView, UpdateAPIView, GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from amuse.settings.constants import NONLOCALIZED_PAYMENTS_COUNTRY

from amuse import mixins as logmixins
from amuse.analytics import (
    subscription_changed,
    subscription_new_started,
    subscription_tier_upgraded,
)
from amuse.api.base.views.exceptions import (
    ActiveSubscriptionExistsError,
    Adyen3DSRequiredError,
    NoActiveSubscriptionExistsError,
    WrongAPIversionError,
    SubscriptionPlanDoesNotExist,
)
from amuse.api.v4.serializers.subscription import (
    AppleSubscriptionSerializer as AppleSubscriptionV4Serializer,
    ChangeSubscriptionSerializer,
    SubscriptionSerializer as SubscriptionV4Serializer,
)
from amuse.api.v5.serializers.subscription import (
    SubscriptionSerializer as SubscriptionV5Serializer,
    AppleSubscriptionSerializer as AppleSubscriptionV5Serializer,
)
from amuse.permissions import CanManageAdyenSubscription, FrozenUserPermission
from amuse.platform import PlatformHelper
from amuse.utils import get_ip_address
from amuse.vendor.adyen import upgrade_subscription_tier
from payments.models import PaymentTransaction
from subscriptions.helpers import calculate_tier_upgrade_price
from subscriptions.models import SubscriptionPlan, Subscription
from users.models import User
from subscriptions.models import SubscriptionPlan


logger = logging.getLogger(__name__)


@permission_classes([IsAuthenticated, FrozenUserPermission, CanManageAdyenSubscription])
class CreateAdyenSubscriptionView(logmixins.LogMixin, CreateAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.request.version not in ['4', '5']:
            raise WrongAPIversionError()

    def get_serializer_class(self):
        if self.request.version == '4':
            return SubscriptionV4Serializer
        elif self.request.version == '5':
            return SubscriptionV5Serializer
        else:
            raise WrongAPIversionError()

    def post(self, request, *args, **kwargs):
        user = request.user
        current_subscription = user.current_subscription()

        if user.tier != User.TIER_FREE:
            if current_subscription and (
                current_subscription.valid_until is None or current_subscription.is_free
            ):
                raise ActiveSubscriptionExistsError()
        is_reactivate = (
            current_subscription and current_subscription.valid_until is not None
        )

        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            response = serializer.save(is_reactivate)
            headers = self.get_success_headers(serializer.data)
            subscription = request.user.current_subscription()
            client = request.META.get('HTTP_USER_AGENT', '')
            ip_address = get_ip_address(request)

            is_localised_price = not request.version == '4'
            country = (
                NONLOCALIZED_PAYMENTS_COUNTRY
                if not is_localised_price
                else serializer.validated_data['country'].code
            )

            latest_payment = subscription.latest_payment()
            latest_payment.category = PaymentTransaction.CATEGORY_INITIAL
            latest_payment.save()

            subscription_new_started(
                subscription,
                PlatformHelper.from_payment(latest_payment),
                client,
                ip_address,
                country,
            )
            return Response(response, status=status.HTTP_201_CREATED, headers=headers)
        except Adyen3DSRequiredError as e:
            return Response(e.adyen_response, status=status.HTTP_200_OK)


@permission_classes([IsAuthenticated, FrozenUserPermission, CanManageAdyenSubscription])
class CreateAppleSubscriptionView(logmixins.LogMixin, CreateAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.request.version not in ['4', '5']:
            raise WrongAPIversionError()
        if self.request.user.tier != User.TIER_FREE:
            raise ActiveSubscriptionExistsError()

    def get_serializer_class(self):
        if self.request.version == '4':
            return AppleSubscriptionV4Serializer
        elif self.request.version == '5':
            return AppleSubscriptionV5Serializer
        else:
            raise WrongAPIversionError()


@permission_classes([IsAuthenticated, CanManageAdyenSubscription])
class ChangeSubscriptionPlanView(logmixins.LogMixin, UpdateAPIView):
    serializer_class = ChangeSubscriptionSerializer

    def get_object(self):
        subscription = self.request.user.current_subscription()
        if not subscription or subscription.is_free:
            raise NoActiveSubscriptionExistsError()
        else:
            return subscription

    def get_new_plan(self):
        plan_id = self.request.data.get('plan')
        try:
            plan_qs = SubscriptionPlan.objects.filter(id=plan_id)
            if plan_id is None or not plan_qs:
                raise SubscriptionPlanDoesNotExist
            return plan_qs.first()
        except Exception as e:
            logger.warning(
                f'Error getting new plan plan_id={plan_id} user_id={self.request.user.pk}'
            )
            raise SubscriptionPlanDoesNotExist

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.request.version == '4':
            raise WrongAPIversionError()

    def update(self, request, *args, **kwargs):
        subscription = self.get_object()
        previous_plan = subscription.plan
        country = subscription.latest_payment().country
        new_plan = self.get_new_plan()

        super().update(request, *args, **kwargs)

        subscription_changed(
            self.get_object(),
            previous_plan,
            new_plan,
            request.META.get('HTTP_USER_AGENT', ''),
            get_ip_address(request),
            country.code,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@permission_classes([IsAuthenticated, FrozenUserPermission, CanManageAdyenSubscription])
class AdyenTierUpgradeView(logmixins.LogMixin, GenericAPIView):
    serializer_class = SubscriptionV5Serializer

    def validate(self):
        subscription = self.request.user.current_entitled_subscription()
        if not subscription or subscription.is_free:
            raise NoActiveSubscriptionExistsError()

        try:
            plan_id = self.kwargs.get('plan_id')
            new_plan = SubscriptionPlan.objects.get(pk=plan_id)
        except SubscriptionPlan.DoesNotExist:
            raise NotFound('The specified Subscription Plan does not exist.')

        if new_plan.tier == subscription.plan.tier:
            raise ValidationError(
                'Unable to upgrade tier, new and current tier are the same'
            )

        # disable all upgrades except BOOST Tier -> PRO Tier upgrades
        if not (
            new_plan.tier == SubscriptionPlan.TIER_PRO
            and subscription.plan.tier == SubscriptionPlan.TIER_PLUS
        ):
            raise ValidationError(
                'Upgrades are only possible from BOOST Tier to PRO Tier'
            )

        return subscription, new_plan

    def get(self, request, *args, **kwargs):
        subscription, new_plan = self.validate()

        try:
            upgrade_price, currency = calculate_tier_upgrade_price(
                subscription, new_plan
            )
        except ValueError as err:
            raise ValidationError(
                f'Error while calculating Tier upgrade price: {str(err)}'
            )

        data = {
            'current_plan': subscription.plan.pk,
            'new_plan': new_plan.pk,
            'upgrade_price': str(upgrade_price),
            'currency': currency.code,
            'upgrade_price_display': f'{currency.code} {str(upgrade_price)}',
        }
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        subscription, new_plan = self.validate()
        previous_plan = subscription.plan

        try:
            upgrade_price, currency = calculate_tier_upgrade_price(
                subscription, new_plan
            )
            custom_price = {'amount': upgrade_price, 'currency': currency}
        except ValueError as err:
            raise ValidationError(
                f'Error while calculating Tier upgrade price: {str(err)}'
            )

        use_existing_payment = (
            self.request.GET.get('use_existing_payment_info', 'true') == 'true'
        )
        if use_existing_payment:
            result = upgrade_subscription_tier(subscription, new_plan, custom_price)
        else:
            try:
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                result = serializer.save(custom_price=custom_price)
            except Adyen3DSRequiredError as e:
                return Response(e.adyen_response, status=status.HTTP_200_OK)

        success = result.get('is_success', False)
        if success:
            new_subscription = request.user.current_subscription()
            latest_payment = new_subscription.latest_payment()
            latest_payment.category = PaymentTransaction.CATEGORY_INITIAL
            latest_payment.save()

            subscription_tier_upgraded(
                new_subscription,
                previous_plan,
                request.META.get('HTTP_USER_AGENT', ''),
                get_ip_address(request),
                latest_payment.country.code,
            )

            return Response(
                data={'is_success': success}, status=status.HTTP_201_CREATED
            )
        else:
            error_msg = result.get(
                'error_message', 'Unknown error, please contact Customer Support'
            )
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    'is_success': success,
                    'details': f'An error occurred while upgrading Subscription Tier for Subscription {subscription.pk}: {error_msg}',
                },
            )
