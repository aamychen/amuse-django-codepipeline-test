import responses
import json
from decimal import Decimal
from django.test import TestCase, override_settings
from django.db import IntegrityError

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from payouts.tests.factories import (
    ProviderFactory,
    PayeeFactory,
    TransferMethodFactory,
    PaymentFactory,
    EventFactory,
    TransferMethodCofigurationFactory,
)
from payouts.models import Payee, Provider, Payment
from countries.tests.factories import CountryFactory, CurrencyFactory
from users.tests.factories import UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class PayoutModelsTestCase(TestCase):
    @responses.activate
    def test_provider_model(self):
        add_zendesk_mock_post_response()
        provider = ProviderFactory()
        assert isinstance(provider.name, str)
        assert isinstance(provider.external_id, str)
        assert provider.active == True
        self.assertEqual(provider.__str__(), provider.name)

    @responses.activate
    def test_payee_model(self):
        add_zendesk_mock_post_response()
        payee = PayeeFactory()
        self.assertIsNotNone(payee.user.id)
        self.assertIsNotNone(payee.external_id)
        self.assertIsInstance(payee.external_id, str)
        self.assertEqual(payee.status, "PRE_ACTIVATED")
        self.assertEqual(payee.verification_status, "NOT_REQUIRED")
        self.assertEqual(payee.type, Payee.TYPE_INDIVIDUAL)
        self.assertIsNotNone(payee.created)
        self.assertEqual(payee.__str__(), payee.user.email)
        # Test government_id values
        gov_ids = [None, "", "911209-4512"]
        for value in gov_ids:
            payee.government_id = value
            payee.save()
        assert payee.government_id == "911209-4512"

    @responses.activate
    def test_transfer_method_model(self):
        add_zendesk_mock_post_response()
        transfer_method = TransferMethodFactory()
        self.assertIsInstance(transfer_method.external_id, str)
        self.assertIsInstance(transfer_method.payee, Payee)
        self.assertEqual(transfer_method.status, "ACTIVATED")
        self.assertEqual(transfer_method.type, "BANK_ACCOUNT")
        self.assertIsInstance(transfer_method.provider, Provider)
        self.assertIsNotNone(transfer_method.created)
        self.assertEqual(
            transfer_method.__str__(), "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
        )

    @responses.activate
    def test_payment_model(self):
        add_zendesk_mock_post_response()
        payment = PaymentFactory()
        self.assertIsInstance(payment.payee, Payee)
        self.assertIsInstance(payment.external_id, str)
        self.assertIsInstance(payment.amount, Decimal)
        self.assertEqual(payment.status, "COMPLETED")
        self.assertIsNotNone(payment.created)
        self.assertEqual(payment.__str__(), "pmt-87939c73-ff0a-4011-970e-3de855347ea7")
        self.assertEqual(payment.payment_type, Payment.TYPE_UNKNOWN)

    @responses.activate
    def test_event_model(self):
        add_zendesk_mock_post_response()
        event = EventFactory()
        self.assertIsInstance(event.object_id, str)
        self.assertEqual(event.reason, "WEBHOOK")
        self.assertEqual(event.initiator, "SYSTEM")
        json_payload = json.loads(event.payload)

        self.assertIsNotNone(json_payload.get("object"))
        self.assertIsInstance(json_payload.get("object"), dict)
        self.assertEqual(event.__str__(), "trm-56b976c5-26b2-42fa-87cf-14b3366673c6")

    @responses.activate
    def test_transfer_method_configuration_model(self):
        add_zendesk_mock_post_response()
        trm_conf = TransferMethodCofigurationFactory()
        self.assertIsInstance(trm_conf.type, str)
        self.assertIsNotNone(trm_conf.currency)
        self.assertIsNotNone(trm_conf.country)
        self.assertIsNotNone(trm_conf.fee)
        self.assertIsNotNone(trm_conf.limits)
        self.assertIsInstance(json.loads(trm_conf.fee), dict)
        self.assertIsInstance(json.loads(trm_conf.limits), dict)
        self.assertTrue(trm_conf.__str__().__contains__("BANK_ACCOUNT"))

    @responses.activate
    def test_trm_get_limit_and_fee(self):
        add_zendesk_mock_post_response()

        # Test defaults
        trm = TransferMethodFactory(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b33666745x"
        )
        limits_and_fee = trm.get_limits_and_fee()
        # {'min_amount': Decimal('35'), 'max_amount': Decimal('100000'), 'fee': Decimal('35')}
        self.assertEqual(limits_and_fee['min_amount'], 2.0)
        self.assertEqual(limits_and_fee['max_amount'], 20000.0)
        self.assertEqual(limits_and_fee['fee'], 1.0)

        # Test defaults PAYPAL_ACCOUNT
        trm_pp = TransferMethodFactory(
            type="PAYPAL_ACCOUNT",
            external_id="trm-56b976c5-26b2-42fa-87cf-14b33666745y",
        )
        limits_and_fee = trm_pp.get_limits_and_fee()
        # {'min_amount': Decimal('35'), 'max_amount': Decimal('100000'), 'fee': Decimal('35')}
        self.assertEqual(limits_and_fee['min_amount'], 2.0)
        self.assertEqual(limits_and_fee['max_amount'], 20000.0)
        self.assertEqual(limits_and_fee['fee'], 1.0)

        # Test get value from TransferMethodCofiguration
        user = UserFactory(country="SE")
        payee = PayeeFactory(user=user)
        currency = CurrencyFactory(code="SEK")
        country = CountryFactory(code="SE", name="Sweden")

        trm_ba = TransferMethodFactory(
            payee=payee,
            currency=currency,
        )

        trm_conf = TransferMethodCofigurationFactory(
            country=country,
            currency=currency,
        )

        limits_and_fee = trm_ba.get_limits_and_fee()
        # {'min_amount': Decimal('35'), 'max_amount': Decimal('100000'), 'fee': Decimal('2')}
        self.assertEqual(limits_and_fee['fee'], 2.00)
        self.assertEqual(limits_and_fee['max_amount'], 100000.00)
        self.assertEqual(limits_and_fee['min_amount'], 35.0)

    @responses.activate
    def test_trm_external_id_unique_constrain(self):
        add_zendesk_mock_post_response()
        trm = TransferMethodFactory(
            external_id="trm-56b976c5-26b2-42fa-87cf-14b33666745x"
        )
        # Test Integrity error was thrown on duplicate external_id
        with self.assertRaises(IntegrityError):
            trm = TransferMethodFactory(
                external_id="trm-56b976c5-26b2-42fa-87cf-14b33666745x"
            )
