from ..purchase_subscription import PurchaseSubscription


class HandlerArgs(object):
    notification_type: int
    purchase_token: str
    google_subscription_id: str
    purchase: PurchaseSubscription

    def __init__(
        self,
        notification_type: int,
        purchase_token: str,
        google_subscription_id: str,
        purchase: PurchaseSubscription,
    ):
        self.notification_type = notification_type
        self.purchase_token = purchase_token
        self.google_subscription_id = google_subscription_id
        self.purchase = purchase
