from users.models import User
from .containers import HandlerArgs
from ..enums import ProcessingResult


class CreateNew:
    def create(self, event_id: str, data: HandlerArgs):
        USER_ID = 50
        google_subscription_id = data.google_subscription_id
        purchase_token = data.purchase_token

        user = User.objects.get(pk=USER_ID)

        from subscriptions.vendor.google.processors.subscription_creator import (
            SubscriptionCreator,
        )

        validated_data = {
            'google_subscription_id': data.google_subscription_id,
            'purchase_token': data.purchase_token,
        }

        SubscriptionCreator().create_from_user_endpoint(event_id, user, validated_data)

        return ProcessingResult.SUCCESS
