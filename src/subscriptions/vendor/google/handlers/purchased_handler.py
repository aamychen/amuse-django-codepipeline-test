import base64

from django.db import transaction

from users.models import User
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from .purchased_handler_v1 import PurchasedNotificationHandlerV1
from .purchased_handler_v2 import PurchasedNotificationHandlerV2


class PurchasedNotificationHandler(AbstractNotificationHandler):
    @transaction.atomic
    def handle(self, data: HandlerArgs):
        user = self.get_user(data)
        if user:
            return PurchasedNotificationHandlerV2(self.event_id, user).handle(data)

        return PurchasedNotificationHandlerV1(self.event_id).handle(data)

    def get_user(self, data: HandlerArgs):
        # obfuscatedExternalAccountId field contains user_id (base64 format).
        # Previous statement is true since (approx.) middle of the June, 2021. For older subscriptions, obfuscatedExternalAccountId is None.
        # With user_id we are able to create google subscription immediately.
        user_id_b64 = data.purchase.obfuscated_external_account_id
        if not user_id_b64:
            return None

        user_id = int(base64.b64decode(user_id_b64).decode())
        return User.objects.get(pk=user_id)
