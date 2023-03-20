from decimal import Decimal

from django.test import TestCase
from factory import Faker

from subscriptions.vendor.google import PurchaseSubscription
from subscriptions.vendor.google.enums import PaymentState
from subscriptions.vendor.google.helpers import convert_msepoch_to_dt
from subscriptions.vendor.google.purchase_subscription import IntroductoryPriceInfo


def to_dt(val):
    return convert_msepoch_to_dt(int(val))


class TestPurchaseSubscription(TestCase):
    def test_default_values(self):
        payload = {
            "startTimeMillis": "1610464079788",
            "expiryTimeMillis": "1610466292906",
            "autoResumeTimeMillis": "1610466292906",
            "userCancellationTimeMillis": "1610466292906",
            "autoRenewing": "1",
            "priceCurrencyCode": "USD",
            "priceAmountMicros": "990000",
            'introductoryPriceInfo': {
                'introductoryPriceCurrencyCode': 'BAM',
                'introductoryPriceAmountMicros': '890000',
                'introductoryPricePeriod': 'P1W',
                'introductoryPriceCycles': '1',
            },
            "countryCode": "BA",
            "developerPayload": "Mica Maca",
            "cancelReason": 1,
            "orderId": "GPA.3371-2429-1583-32674..5",
            "purchaseType": 0,
            "acknowledgementState": 1,
            "kind": "androidpublisher#subscriptionPurchase",
            "paymentState": 2,
            "purchaseToken": Faker('name'),
            "linkedPurchaseToken": Faker('name'),
            "profileName": Faker('name'),
            "emailAddress": Faker('email'),
            "givenName": Faker('name'),
            "familyName": Faker('name'),
            "profileId": Faker('name'),
            'externalAccountId': Faker('name'),
            'promotionType': 1,
            'promotionCode': Faker('name'),
            'obfuscatedExternalAccountId': Faker('name'),
            'obfuscatedExternalProfileId': Faker('name'),
        }

        purchase = PurchaseSubscription(**payload)
        self.assertEqual(payload, purchase.payload)
        self.assertEqual(payload['kind'], purchase.kind)
        self.assertEqual(to_dt(payload['startTimeMillis']), purchase.start)
        self.assertEqual(to_dt(payload['expiryTimeMillis']), purchase.expiry_date)
        self.assertEqual(
            to_dt(payload['autoResumeTimeMillis']), purchase.auto_resume_time_millis
        )
        self.assertEqual(True, purchase.auto_renewing)
        self.assertEqual(payload['priceCurrencyCode'], purchase.price_currency_code)
        self.assertEqual(Decimal('0.99'), purchase.price_amount)
        self.assertEqual(payload['countryCode'], purchase.country_code)
        self.assertEqual(payload['developerPayload'], purchase.developer_payload)
        self.assertEqual(PaymentState.FREE_TRIAL, purchase.payment_state)
        self.assertEqual(payload['cancelReason'], purchase.cancel_reason)
        self.assertEqual(
            to_dt(payload['userCancellationTimeMillis']),
            purchase.user_cancellation_time,
        )
        self.assertEqual(payload['orderId'], purchase.order_id)
        self.assertEqual(payload['linkedPurchaseToken'], purchase.linked_purchase_token)
        self.assertEqual(payload['purchaseToken'], purchase.purchase_token)
        self.assertEqual(payload['profileName'], purchase.profile_name)
        self.assertEqual(payload['emailAddress'], purchase.email_address)
        self.assertEqual(payload['givenName'], purchase.given_name)
        self.assertEqual(payload['familyName'], purchase.family_name)
        self.assertEqual(payload['profileId'], purchase.profile_id)
        self.assertEqual(
            payload['acknowledgementState'], purchase.acknowledgement_state
        )
        self.assertEqual(payload['externalAccountId'], purchase.external_account_id)
        self.assertEqual(payload['promotionType'], purchase.promotion_type)
        self.assertEqual(payload['promotionCode'], purchase.promotion_code)
        self.assertEqual(
            payload['obfuscatedExternalAccountId'],
            purchase.obfuscated_external_account_id,
        )
        self.assertEqual(
            payload['obfuscatedExternalProfileId'],
            purchase.obfuscated_external_profile_id,
        )

        introductory_info = purchase.introductory_price_info
        introductory_payload = payload.get('introductoryPriceInfo')

        self.assertIsNotNone(introductory_info)
        self.assertIsNotNone(introductory_payload)
        self.assertIsNotNone(introductory_info.price_currency_code)
        self.assertIsNotNone(introductory_info.price_amount)
        self.assertIsNotNone(introductory_info.price_period)
        self.assertIsNotNone(introductory_info.price_cycles)

    def test_alternative_values(self):
        payload = {}

        purchase = PurchaseSubscription(**payload)
        self.assertEqual(payload, purchase.payload)
        self.assertIsNone(purchase.start)
        self.assertIsNone(purchase.expiry_date)
        self.assertIsNone(purchase.auto_resume_time_millis)
        self.assertEqual(False, purchase.auto_renewing)
        self.assertEqual(Decimal('0.0'), purchase.price_amount)
        self.assertIsNone(purchase.user_cancellation_time)
        self.assertIsNone(purchase.introductory_price_info)


class TestIntroductoryPriceInfo(TestCase):
    def test_default_values(self):
        payload = {
            'introductoryPriceCurrencyCode': 'BAM',
            'introductoryPriceAmountMicros': '890000',
            'introductoryPricePeriod': 'P1W',
            'introductoryPriceCycles': '1',
        }

        introductory_info = IntroductoryPriceInfo(**payload)

        self.assertEqual(
            payload['introductoryPriceCurrencyCode'],
            introductory_info.price_currency_code,
        )
        self.assertEqual(Decimal('0.89'), introductory_info.price_amount)
        self.assertEqual(
            payload['introductoryPricePeriod'], introductory_info.price_period
        )
        self.assertEqual(
            int(payload['introductoryPriceCycles']), introductory_info.price_cycles
        )

    def test_alternative_values(self):
        payload = {}
        introductory_info = IntroductoryPriceInfo(**payload)
        self.assertEqual(Decimal('0.00'), introductory_info.price_amount)
