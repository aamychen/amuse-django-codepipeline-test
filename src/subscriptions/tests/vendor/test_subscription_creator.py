from decimal import Decimal

import pytest

from payments.models import PaymentTransaction
from subscriptions.vendor.google import PurchaseSubscription
from subscriptions.vendor.google.processors.subscription_creator import (
    SubscriptionCreator,
    ChargedPrice,
)


@pytest.mark.parametrize(
    "payload,category,expected",
    [
        ({}, PaymentTransaction.CATEGORY_INITIAL, False),
        ({'introductoryPriceInfo': {}}, PaymentTransaction.CATEGORY_RENEWAL, False),
        ({'introductoryPriceInfo': {}}, PaymentTransaction.CATEGORY_INITIAL, True),
    ],
)
def test_is_in_introductory_price_period(payload, category, expected):
    purchase = PurchaseSubscription(**payload)
    actual = SubscriptionCreator()._is_in_introductory_price_period(purchase, category)
    assert expected == actual


@pytest.mark.parametrize(
    "payload,payment_type,is_in_ipp,is_upgrade,expected",
    [
        (
            {'priceAmountMicros': '1990000', 'priceCurrencyCode': 'USD'},
            PaymentTransaction.TYPE_PAYMENT,
            False,
            False,
            {'price': Decimal('1.99'), 'currency': 'USD'},
        ),
        (
            {'priceAmountMicros': '1990000', 'priceCurrencyCode': 'USD'},
            PaymentTransaction.TYPE_PAYMENT,
            False,
            True,
            {'price': Decimal('0.00'), 'currency': 'USD'},
        ),
        (
            {'priceAmountMicros': '1990000', 'priceCurrencyCode': 'USD'},
            PaymentTransaction.TYPE_FREE_TRIAL,
            False,
            False,
            {'price': Decimal('0.00'), 'currency': 'USD'},
        ),
        (
            {
                'introductoryPriceInfo': {
                    'introductoryPriceAmountMicros': '1890000',
                    'introductoryPriceCurrencyCode': 'USD',
                }
            },
            PaymentTransaction.TYPE_PAYMENT,
            True,
            False,
            {'price': Decimal('1.89'), 'currency': 'USD'},
        ),
    ],
)
def test_charged_price(payload, payment_type, is_in_ipp, is_upgrade, expected):
    purchase = PurchaseSubscription(**payload)
    charged_price = ChargedPrice(purchase, payment_type, is_in_ipp, is_upgrade)

    assert charged_price.amount == expected['price']
    assert charged_price.currency_code == expected['currency']
