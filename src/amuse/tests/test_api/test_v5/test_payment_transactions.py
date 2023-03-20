from decimal import Decimal
import pytest
from django.urls import reverse
from rest_framework import status

from amuse.tests.test_api.base import AmuseAPITestCase, API_V5_ACCEPT_VALUE
from countries.tests.factories import CountryFactory
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.tests.factories import (
    SubscriptionFactory,
    SubscriptionPlanFactory,
    PriceCardFactory,
)
from users.tests.factories import UserFactory


class PaymentTransactionTestCase(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.country = CountryFactory()
        self.plan = SubscriptionPlanFactory(countries=[self.country])
        self.card = self.plan.pricecard_set.first()
        self.subscription = SubscriptionFactory(plan=self.plan, user=self.user)
        self.transaction = PaymentTransactionFactory(
            user=self.user,
            vat_amount=Decimal("1.00"),
            plan=self.plan,
            subscription=self.subscription,
            country=self.country,
            currency=self.card.currency,
        )
        self.other_transaction = PaymentTransactionFactory()
        self.url = reverse('payment-transactions')
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)

    def test_only_own_transactions_visible(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        payload = response.json()
        self.assertEqual(len(payload), 1)
        transaction = payload[0]
        self.assertEqual(transaction['id'], self.transaction.pk)
        self.assertEqual(transaction['country']['code'], self.transaction.country.code)
        self.assertEqual(
            transaction['subscription']['plan']['id'],
            self.transaction.subscription.plan_id,
        )
        self.assertEqual(transaction['amount'], str(self.transaction.amount))
        amount = '{:f}'.format(Decimal(transaction['amount']).normalize())
        self.assertEqual(
            transaction['amount_display'], f'{self.card.currency.code} {amount}'
        )
        vat_amount = '{:f}'.format(Decimal(transaction['vat_amount']).normalize())
        self.assertEqual(
            transaction['vat_amount_display'], f'{self.card.currency.code} {vat_amount}'
        )
        self.assertEqual(transaction['currency'], self.card.currency.code)
        self.assertEqual(transaction['vat_amount'], str(self.transaction.vat_amount))
        self.assertEqual(
            Decimal(transaction['vat_percentage']),
            Decimal(self.transaction.vat_percentage),
        )
        self.assertEqual(
            transaction['external_transaction_id'],
            self.transaction.external_transaction_id,
        )
        self.assertEqual(transaction['type'], self.transaction.get_type_display())

    def test_missing_card_returns_400(self):
        self.plan.pricecard_set.all().delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            [
                f'No PriceCard found for Plan {self.plan.name} (id={self.plan.pk}) and Country {self.country.code}'
            ],
        )

    def test_display_vat_amount_sek_for_SE_transactions_non_SEK_currency(self):
        self.user2 = UserFactory()
        self.SE_country = CountryFactory(code='SE')
        self.other_plan = SubscriptionPlanFactory(
            name='Random Campaign', countries=[self.SE_country]
        )
        self.other_card = self.other_plan.pricecard_set.first()
        self.other_subscription = SubscriptionFactory(
            plan=self.other_plan, user=self.user2
        )
        self.SE_transaction = PaymentTransactionFactory(
            user=self.user2,
            vat_amount=Decimal("1.00"),
            vat_amount_sek=Decimal("10"),
            plan=self.other_plan,
            subscription=self.other_subscription,
            country=self.SE_country,
            currency=self.other_card.currency,
        )
        self.client.force_authenticate(self.user2)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        payload = response.json()
        self.assertEqual(len(payload), 1)
        transaction = payload[0]

        vat_amount_sek = '{:f}'.format(
            Decimal(self.SE_transaction.vat_amount_sek).normalize()
        )
        self.assertEqual(transaction['vat_amount_display'], f'SEK {vat_amount_sek}')


class PaymentTransactionReturnOnlyValidTypesTestCase(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.country = CountryFactory()
        self.plan = SubscriptionPlanFactory(countries=[self.country])
        self.card = self.plan.pricecard_set.first()
        self.subscription = SubscriptionFactory(plan=self.plan, user=self.user)
        self.url = reverse('payment-transactions')
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)
        self.INVALID_TYPES = [PaymentTransaction.TYPE_UNKNOWN]

    def test_type_of_transaction(self):
        for payment_type in PaymentTransaction.TYPE_CHOICES:
            PaymentTransactionFactory(
                user=self.user,
                vat_amount=Decimal("1.00"),
                plan=self.plan,
                subscription=self.subscription,
                country=self.country,
                currency=self.card.currency,
                type=payment_type[0],
            )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        payload = response.json()

        count_valid_types = len(PaymentTransaction.TYPE_CHOICES) - len(
            self.INVALID_TYPES
        )
        self.assertEqual(len(payload), count_valid_types)

        for payment_type in PaymentTransaction.TYPE_CHOICES:
            transactions = filter(lambda x: x['type'] == payment_type[1], payload)
            expected_count = 0 if payment_type[0] in self.INVALID_TYPES else 1
            self.assertEqual(len(list(transactions)), expected_count)
