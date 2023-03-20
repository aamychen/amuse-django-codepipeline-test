from datetime import datetime
from decimal import Decimal
from typing import Optional

from .helpers import convert_msepoch_to_dt, convert_microunits_to_currency_price
from .enums import PaymentState, AcknowledgementState, CancelReason


class IntroductoryPriceInfo(object):
    """
    Contains the introductory price information for a subscription.

    https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions#introductorypriceinfo
    """

    def __init__(self, *args, **kwargs):
        self.payload = kwargs

    @property
    def price_currency_code(self) -> str:
        """
        ISO 4217 currency code for the introductory subscription price. For example, if
        the price is specified in British pounds sterling, priceCurrencyCode is "GBP".
        """
        return self.payload.get('introductoryPriceCurrencyCode')

    @property
    def price_amount(self) -> Decimal:
        """
        Introductory price of the subscription, not including tax. The currency is the
        same as priceCurrencyCode. Price is expressed in micro-units, where 1,000,000
        micro-units represents one unit of the currency. For example, if the
        subscription price is €1.99, priceAmountMicros is 1990000.
        """
        price_amount_micros = self.payload.get('introductoryPriceAmountMicros')
        if price_amount_micros is None:
            return Decimal('0.0')

        return convert_microunits_to_currency_price(int(price_amount_micros))

    @property
    def price_period(self) -> str:
        """
        Introductory price period, specified in ISO 8601 format. Common values are
        (but not limited to) "P1W" (one week), "P1M" (one month), "P3M" (three months),
        "P6M" (six months), and "P1Y" (one year).
        """
        return self.payload.get('introductoryPricePeriod')

    @property
    def price_cycles(self) -> int:
        """
        The number of billing period to offer introductory pricing.
        """
        return int(self.payload.get('introductoryPriceCycles'))


class PurchaseSubscription(object):
    """
    A SubscriptionPurchase resource indicates the status of a user's subscription purchase.

    https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions#resource:-subscriptionpurchase
    """

    def __init__(self, *args, **kwargs):
        self.payload = kwargs
        # Information provided by the user when they complete the subscription cancellation flow (cancellation reason survey).
        # cancelSurveyResult: NOTE NotImplemented

        # The latest price change information available. This is present only when there is an upcoming price change for the subscription yet to be applied.
        #
        # Once the subscription renews with the new price or the subscription is canceled, no price change information will be returned.
        # priceChange: NOTE NotImplemented

    @property
    def kind(self):
        """
        This kind represents a subscriptionPurchase object in the androidpublisher service.
        """
        return self.payload.get('kind')

    @property
    def start(self) -> datetime:
        """
        Time at which the subscription was granted, as datetime.
        """
        start = self.payload.get('startTimeMillis')
        if start is None:
            return None

        return convert_msepoch_to_dt(int(start))

    @property
    def expiry_date(self) -> datetime:
        """
        Expiry time in date format
        """
        expiry_time_ms = self.payload.get('expiryTimeMillis')
        if expiry_time_ms is None:
            return None

        return convert_msepoch_to_dt(int(expiry_time_ms))

    @property
    def auto_resume_time_millis(self) -> datetime:
        """
        # Time at which the subscription will be automatically resumed, as date.
        Only present if the user has requested to pause the subscription.
        """
        auto_resume_ms = self.payload.get('autoResumeTimeMillis')
        if auto_resume_ms is None:
            return None

        return convert_msepoch_to_dt(int(auto_resume_ms))

    @property
    def auto_renewing(self) -> bool:
        """Whether the subscription will automatically be renewed when it reaches its current expiry time."""
        return self.payload.get('autoRenewing') in ['True', 'true', 1, '1']

    @property
    def price_currency_code(self):
        """ISO 4217 currency code for the subscription price.
        For example, if the price is specified in British pounds sterling, priceCurrencyCode is "GBP".
        """
        return self.payload.get('priceCurrencyCode')

    @property
    def price_amount(self):
        """
        Price of the subscription, not including tax. priceAmountMicros is expressed in
        micro-units, where 1,000,000 micro-units represents one unit of the currency.

        For example, if the subscription price is €1.99, priceAmountMicros is 1990000.
        This property returns real price.
        """
        price_amount_micros = self.payload.get('priceAmountMicros')

        if price_amount_micros is None:
            return Decimal('0.0')

        return convert_microunits_to_currency_price(int(price_amount_micros))

    @property
    def introductory_price_info(self) -> Optional[IntroductoryPriceInfo]:
        """
        Introductory price information of the subscription.

        This is only present when the subscription was purchased with an introductory price.

        NOTE: This field does not indicate the subscription is currently in
        introductory price period.
        """
        intro_price_info = self.payload.get('introductoryPriceInfo')

        if intro_price_info is None:
            return None

        return IntroductoryPriceInfo(**intro_price_info)

    @property
    def country_code(self):
        """
        ISO 3166-1 alpha-2 billing country/region code of the user at the time the subscription was granted.
        """
        return self.payload.get("countryCode")

    @property
    def developer_payload(self):
        """A developer-specified string that contains supplemental information about an order."""
        return self.payload.get('developerPayload')

    @property
    def payment_state(self):
        """
        The payment state of the subscription.
        Possible values are:
            - 0. Payment pending
            - 1. Payment received
            - 2. Free trial
            - 3. Pending deferred upgrade/downgrade

        Not present for canceled, expired subscriptions.
        """
        state = self.payload.get('paymentState')

        if state is None:
            return None

        return PaymentState(state)

    @property
    def cancel_reason(self):
        """
        The reason why a subscription was canceled or is not auto-renewing.
        Possible values are:
            - 0. User canceled the subscription
            - 1. Subscription was canceled by the system, for example because of a billing problem
            - 2. Subscription was replaced with a new subscription
            - 3. Subscription was canceled by the developer
        """
        reason = self.payload.get('cancelReason', None)
        if reason is None:
            return None
        return CancelReason(self.payload.get('cancelReason'))

    @property
    def user_cancellation_time(self):
        """
        The time at which the subscription was canceled by the user, as date.
        Only present if cancelReason is 0.
        """
        val = self.payload.get('userCancellationTimeMillis')
        if val is None:
            return None

        return convert_msepoch_to_dt(int(val))

    @property
    def order_id(self):
        """
        The order id of the latest recurring order associated with the purchase of the subscription.
        """
        return self.payload.get('orderId')

    @property
    def linked_purchase_token(self):
        """
        The purchase token of the originating purchase if this subscription is one of
        the following:
            - 0. Re-signup of a canceled but non-lapsed subscription
            - 1. Upgrade/downgrade from a previous subscription

        For example, suppose a user originally signs up and you receive
        purchase token X, then the user cancels and goes through the resignup flow
        (before their subscription lapses) and you receive purchase token Y,
        and finally the user upgrades their subscription and you receive
        purchase token Z.
        If you call this API with purchase token Z, this field will  be set to Y.
        If you call this API with purchase token Y, this field will be  set to X.
        If you call this API with purchase token X,  this field will not be set.
        """
        return self.payload.get('linkedPurchaseToken')

    @property
    def purchase_token(self):
        """
        The type of purchase of the subscription.
        This field is only set if this purchase was not made using the standard in-app billing flow.

        Possible values are:
            - 0. Test (i.e. purchased from a license testing account)
            - 1. Promo (i.e. purchased using a promo code)
        """
        return self.payload.get('purchaseToken')

    @property
    def profile_name(self):
        """
        The profile name of the user when the subscription was purchased.
        Only present for purchases made with 'Subscribe with Google'.
        """
        return self.payload.get('profileName')

    @property
    def email_address(self):
        """
        The email address of the user when the subscription was purchased.
        Only present for purchases made with 'Subscribe with Google'.
        """
        return self.payload.get('emailAddress')

    @property
    def given_name(self):
        """
        The given name of the user when the subscription was purchased.
        Only present for purchases made with 'Subscribe with Google'.
        """
        return self.payload.get('givenName')

    @property
    def family_name(self):
        """
        The family name of the user when the subscription was purchased.
        Only present for purchases made with 'Subscribe with Google'.
        """
        return self.payload.get('familyName')

    @property
    def profile_id(self):
        """
        The Google profile id of the user when the subscription was purchased.
        Only present for purchases made with 'Subscribe with Google'.
        """
        return self.payload.get('profileId')

    @property
    def acknowledgement_state(self):
        """
        The acknowledgement state of the subscription product.
        Possible values are:
            - 0. Yet to be acknowledged
            - 1. Acknowledged
        """
        val = self.payload.get('acknowledgementState')

        if val is None:
            return None

        return AcknowledgementState(int(val))

    @property
    def external_account_id(self):
        """
        User account identifier in the third-party service.
        Only present if account linking happened as part of the subscription purchase flow.
        """
        return self.payload.get('externalAccountId')

    @property
    def promotion_type(self):
        """
        The type of promotion applied on this purchase. This field is only set if a
        promotion is applied when the subscription was purchased.
        Possible values are: 0. One time code 1. Vanity code
        """
        return self.payload.get('promotionType')

    @property
    def promotion_code(self):
        """
        The promotion code applied on this purchase.
        This field is only set if a vanity code promotion is applied when the subscription was purchased.
        """
        return self.payload.get('promotionCode')

    @property
    def obfuscated_external_account_id(self):
        """
        An obfuscated version of the id that is uniquely associated with the user's
        account in your app.

        Present for the following purchases:
            - If account linking happened as part of the subscription purchase flow.
            - It was specified using https://developer.android.com/reference/com/android/billingclient/api/BillingFlowParams.Builder#setobfuscatedaccountid when the purchase was made.
        """
        return self.payload.get('obfuscatedExternalAccountId')

    @property
    def obfuscated_external_profile_id(self):
        """
        An obfuscated version of the id that is uniquely associated with the user's
        profile in your app.

        Only present if specified using https://developer.android.com/reference/com/android/billingclient/api/BillingFlowParams.Builder#setobfuscatedprofileid when the purchase was made.
        """
        return self.payload.get('obfuscatedExternalProfileId')
