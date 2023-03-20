from django.db import transaction

from countries.models import Country, Currency
from subscriptions.rules import ChangeReason
from .abstract_handler import AbstractNotificationHandler
from .containers import HandlerArgs
from ..enums import ProcessingResult
from ..helpers import info
from ..processors.subscription_creator import (
    SubscriptionCreatorArgs,
    SubscriptionCreator,
)


class RecoveredNotificationHandler(AbstractNotificationHandler):
    """
    Recovered is received during PAUSE SCHEDULED period when user RESUMES the subscription.
    Recovered is received during ON HOLD period when user FIX PAYMENT issues.
    """

    @transaction.atomic
    def handle(self, data: HandlerArgs):
        payment_method = self.get_payment_method(data)
        plan = self.get_plan(data)

        user = payment_method.user

        purchase = data.purchase

        paid_until = purchase.expiry_date
        price = purchase.price_amount

        country_code = purchase.country_code
        currency_code = purchase.price_currency_code
        order_id = purchase.order_id

        country = Country.objects.filter(code=country_code.upper()).first()
        currency = Currency.objects.filter(code=currency_code.upper()).first()

        params = SubscriptionCreatorArgs(
            purchase_token=data.purchase_token,
            google_subscription_id=data.google_subscription_id,
            purchase=data.purchase,
            plan=plan,
            change_reason=ChangeReason.GOOGLE_RECOVERED,
            is_renewal=True,
            is_upgrade=False,
            customer_payload=None,
        )
        subscription = SubscriptionCreator().create_from_google_webhook(
            self.event_id, user, params
        )

        info(
            self.event_id,
            f'Subscription RECOVERED (new subscription created), id={subscription.id}',
        )
        return ProcessingResult.SUCCESS
