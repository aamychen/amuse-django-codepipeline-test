import base64

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from amuse import mixins as logmixins
from amuse.analytics import (
    subscription_new_intro_started,
    subscription_new_started,
    subscription_trial_started,
)
from amuse.api.base.views.exceptions import (
    WrongAPIversionError,
    ActiveSubscriptionExistsError,
)
from amuse.api.v5.serializers.subscription import (
    CreateGoogleSubscriptionRequestSerializer,
)
from amuse.permissions import FrozenUserPermission
from amuse.platform import PlatformType
from amuse.utils import get_ip_address
from payments.models import PaymentTransaction
from subscriptions.models import Subscription
from subscriptions.vendor.google import GooglePlayAPI, PurchaseSubscription
from subscriptions.vendor.google.errors import (
    InvalidPurchaseTokenError,
    UserNotEligibleForFreeTrial,
    SubscriptionPlanNotFoundError,
    BaseNotificationError,
    PurchaseTokenAlreadyUsedError,
)
from subscriptions.vendor.google.processors.subscription_creator import (
    SubscriptionCreator,
)
from users.models import User


@permission_classes([IsAuthenticated, FrozenUserPermission])
class CreateGoogleSubscriptionView(logmixins.LogMixin, CreateAPIView):
    def get_serializer_class(self):
        if self.request.version not in ['5']:
            raise WrongAPIversionError()

        return CreateGoogleSubscriptionRequestSerializer

    @staticmethod
    def _trigger_analytics(request, subscription, payment):
        ip = get_ip_address(request)
        client = request.META.get('HTTP_USER_AGENT', '')

        subscription_started_functions = {
            PaymentTransaction.TYPE_FREE_TRIAL: subscription_trial_started,
            PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT: subscription_new_intro_started,
        }
        subscription_started = subscription_started_functions.get(
            payment.type, subscription_new_started
        )

        subscription_started(
            subscription, PlatformType.ANDROID, client, ip, payment.country.code
        )

    @staticmethod
    def _handle_error(err):
        """
        Have to explicitly inspect InvalidPurchaseTokenError,
        UserNotEligibleForFreeTrial abd SubscriptionPlanNotFoundError
        because of backward compatibility

        Function raise ValidationError.
        """
        if isinstance(err, InvalidPurchaseTokenError):
            raise ValidationError({'purchase_token': 'Invalid purchase_token'})

        if isinstance(err, UserNotEligibleForFreeTrial):
            raise ValidationError(
                {'google_subscription_id': 'User is not eligible for free trial'}
            )

        if isinstance(err, SubscriptionPlanNotFoundError):
            raise ValidationError(
                {'google_subscription_id': 'Invalid google_product_id'}
            )

        if isinstance(err, PurchaseTokenAlreadyUsedError):
            raise ValidationError({'purchase_token': 'Already used purchase_token.'})

        raise ValidationError({'error': str(err)})

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        # Validate request
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            google_subscription_id = serializer.validated_data['google_subscription_id']
            purchase_token = serializer.validated_data['purchase_token']

            purchase = self.get_google_purchase(
                request.request_id, google_subscription_id, purchase_token
            )

            user_from_google = self._get_user_from_obfuscated_account_id(purchase)
            is_v2 = user_from_google is not None

            if is_v2:
                # Since (approx.) middle of the June, 2021 subscription is created after we receive a notification from Google.
                # We are able to differentiate version based on obfuscatedExternalAccountId field.
                # v2 won't create new subscription.
                self.process_v2(request, purchase, user_from_google)
            else:
                self.process_v1(request, serializer.validated_data, purchase)
        except BaseNotificationError as err:
            self._handle_error(err)

        return Response(data={'success': True}, status=status.HTTP_201_CREATED)

    def get_google_purchase(self, event_id, google_subscription_id, purchase_token):
        purchase = GooglePlayAPI().verify_purchase_token(
            event_id, google_subscription_id, purchase_token
        )
        if purchase is None:
            raise InvalidPurchaseTokenError(google_subscription_id, purchase_token)

        return PurchaseSubscription(**purchase)

    def process_v1(self, request, validated_data, purchase: PurchaseSubscription):
        user = request.user

        if user.tier != User.TIER_FREE:
            raise ActiveSubscriptionExistsError()

        subscription = SubscriptionCreator().create_from_user_endpoint(
            request.request_id, user, validated_data, purchase
        )
        # analytics
        self._trigger_analytics(request, subscription, subscription.latest_payment())

    def process_v2(
        self, request, purchase: PurchaseSubscription, user_from_google: User
    ):
        qs = Subscription.objects.filter(
            payment_method__external_recurring_id=purchase.purchase_token
        )

        count = qs.count()
        if count == 0:
            raise ValidationError({'purchase_token': 'Subscription not created.'})

        if count > 1:
            raise ValidationError(
                {'purchase_token': 'Multiple subscriptions created. Contact support.'}
            )

        subscription = qs.first()
        if subscription.user != request.user:
            raise ValidationError(
                {
                    'purchase_token': 'Subscription already created. Possible fraud attempt. Contact support.'
                }
            )

        if user_from_google != request.user:
            raise ValidationError(
                {'purchase_token': 'Possible fraud attempt. Contact support.'}
            )

    def _get_user_from_obfuscated_account_id(self, purchase):
        user_id_b64 = purchase.obfuscated_external_account_id
        if not user_id_b64:
            return None

        user_id = int(base64.b64decode(user_id_b64).decode())
        return User.objects.get(pk=user_id)
