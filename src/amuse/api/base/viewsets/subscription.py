from rest_framework import status, viewsets
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from amuse import mixins as logmixins
from amuse.analytics import subscription_canceled
from amuse.api.base.views.exceptions import (
    NoActiveSubscriptionExistsError,
    WrongAPIversionError,
)
from amuse.api.v4.serializers.subscription import (
    CurrentSubscriptionSerializer as CurrentSubscriptionV4Serializer,
)
from amuse.api.v5.serializers.subscription import (
    CurrentSubscriptionSerializer as CurrentSubscriptionV5Serializer,
)
from amuse.permissions import CanDeleteAdyenSubscription
from amuse.utils import get_ip_address


@permission_classes([IsAuthenticated, CanDeleteAdyenSubscription])
class SubscriptionViewSet(logmixins.LogMixin, viewsets.GenericViewSet):
    def get_serializer_class(self):
        if self.request.version == '4':
            return CurrentSubscriptionV4Serializer
        elif self.request.version == '5':
            return CurrentSubscriptionV5Serializer
        else:
            raise WrongAPIversionError()

    def get_object(self):
        if self.request.version == '4':
            return self.request.user.current_subscription()

        return self.request.user.current_entitled_subscription()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.request.version in ['4', '5']:
            raise WrongAPIversionError()

    def list(self, request, *args, **kwargs):
        subscription = self.get_object()
        if subscription is None:
            raise NoActiveSubscriptionExistsError()

        serializer = self.get_serializer(subscription)
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        subscription = self.get_object()
        if not subscription or subscription.is_free or subscription.valid_until:
            raise NoActiveSubscriptionExistsError()

        subscription.valid_until = subscription.paid_until
        subscription.save()
        plan_changes = subscription.plan_changes.all()
        if plan_changes:
            plan_changes.update(valid=False)

        subscription_canceled(
            subscription,
            request.META.get('HTTP_USER_AGENT', ''),
            get_ip_address(request),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
