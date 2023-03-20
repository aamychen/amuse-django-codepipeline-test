from unittest import mock
from releases.models import RoyaltySplit
from decimal import Decimal
from django.test import RequestFactory, TransactionTestCase

from hyperwallet.models import (
    User,
    Payment,
)
from hyperwallet.exceptions import HyperwalletAPIException
from countries.tests.factories import CurrencyFactory
from users.tests.factories import UserFactory
from payouts.tests.factories import ProviderFactory, PayeeFactory, TransferMethodFactory
from releases.tests.factories import RoyaltySplitFactory, SongFactory, ReleaseFactory
from amuse.api.v5.serializers.payout_ffwd import (
    FFWDOfferAcceptSerializer,
)
from payouts.models import Event, Payment as amuse_pmt
from releases.models import release


class TestFFWDOfferAcceptSerializers(TransactionTestCase):
    reset_sequences = True

    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.user = UserFactory(country="US", email='test@example.com')
        self.user_defaults = {
            'addressLine1': "123 Main Street",
            'city': "New York",
            'clientUserId': str(self.user.id),
            'country': self.user.country,
            'dateOfBirth': "1980-01-01",
            'email': self.user.email,
            'firstName': self.user.first_name,
            'lastName': self.user.last_name,
            'postalCode': "10016",
            'profileType': "INDIVIDUAL",
            'programToken': "prg-19d7ef5e-e01e-43bc-b271-79eef1062832",
            'stateProvince': "NY",
            'status': "PRE_ACTIVATED",
            'token': "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7",
            'verificationStatus': "NOT_REQUIRED",
            'profileType': "INDIVIDUAL",
        }
        self.hw_user = User(self.user_defaults)
        self.provide = ProviderFactory(
            name="HW_PROGRAM_WORLD",
            external_id="prg-19d7ef5e-e01e-43bc-b271-79eef1062832",
        )
        self.payee = PayeeFactory(
            user=self.user,
            external_id=self.user_defaults['token'],
            provider=self.provide,
        )
        self.release = ReleaseFactory(status=release.Release.STATUS_RELEASED)
        self.song = SongFactory(
            meta_language=None, meta_audio_locale=None, release=self.release
        )
        self.splits = RoyaltySplitFactory(
            song=self.song,
            user=self.user,
            rate=Decimal("1.0"),
            revision=1,
            status=RoyaltySplit.STATUS_ACTIVE,
            is_owner=True,
        )
        self.trm_defaults = {
            "token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "type": "BANK_ACCOUNT",
        }
        self.trm = TransferMethodFactory(
            payee=self.payee, external_id=self.trm_defaults['token']
        )
        self.to_serializer = {
            "offer_id": "56b976c5-26b2-42fa-87cf-14b3366673c6",
            "destination_token": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
        }
        self.request = RequestFactory().post('/payouts/ffwd/')
        self.request.user = self.user
        self.context = {'request': self.request}
        self.serializer = FFWDOfferAcceptSerializer(
            request=self.request, data=self.to_serializer
        )
        self.serializer.context['request'] = self.request

        self.defaut_response = {
            "amount": "1000.00",
            "clientPaymentId": str(self.payee.pk),
            "createdOn": "2021-07-07T17:57:17",
            "currency": "USD",
            "destinationToken": "trm-56b976c5-26b2-42fa-87cf-14b3366673c6",
            "expiresOn": "2022-01-03T17:57:17",
            "programToken": "prg-4539a19b-c3e1-44a2-9121-23c73c345c46",
            "purpose": "OTHER",
            "status": "IN_PROGRESS",
            "token": "pmt-ebde365d-650f-408f-ac92-3a96b8e66f45",
        }
        self.currency = CurrencyFactory(code='USD')

    @mock.patch(
        "payouts.ffwd.validate_royalty_advance_offer",
        return_value={
            "royalty_advance_offer": {"split_ids_for_locking": [1]},
            "is_valid": True,
            "withdrawal_total": 1000.00,
            "royalty_advance_id": "12345678-1234-1234-1234-123456789123",
        },
    )
    @mock.patch('hyperwallet.Api.createPayment')
    def test_accept_ffwd_success(self, mock_hw_payment_create, *_):
        mock_hw_payment_create.return_value = Payment(self.defaut_response)

        self.assertTrue(self.serializer.is_valid())
        data = self.serializer.save()
        self.assertTrue(data['is_success'])

        # Assert DB data is written
        pmt_db = amuse_pmt.objects.get(external_id=self.defaut_response['token'])
        self.assertEqual(pmt_db.status, 'IN_PROGRESS')
        self.assertEqual(pmt_db.amount, Decimal('1000.00'))
        self.assertEqual(pmt_db.currency.code, 'USD')
        self.assertEqual(pmt_db.payment_type, amuse_pmt.TYPE_ADVANCE)
        self.assertEqual(
            pmt_db.revenue_system_id, '12345678-1234-1234-1234-123456789123'
        )

        pmt_event = Event.objects.get(object_id=self.defaut_response['token'])

        self.assertEqual(pmt_event.reason, "API call")
        self.assertEqual(pmt_event.initiator, "SYSTEM")
        self.assertEqual(pmt_event.payload['status'], "IN_PROGRESS")

    @mock.patch(
        "payouts.ffwd.validate_royalty_advance_offer",
        return_value={
            "royalty_advance_offer": {"split_ids_for_locking": [1]},
            "is_valid": True,
            "withdrawal_total": 1000.00,
            "royalty_advance_id": 12345678 - 1234 - 1234 - 1234 - 123456789123,
        },
    )
    @mock.patch(
        "amuse.api.v5.serializers.payout_ffwd.update_royalty_advance_offer",
        return_value={"advance_id": "12345678-1234-1234-1234-123456789123"},
    )
    @mock.patch('hyperwallet.Api.createPayment')
    @mock.patch('payouts.ffwd.FFWDHelpers.unlock_splits')
    def test_accept_ffwd_failed_and_canceled(
        self,
        mock_unlock_fn,
        mock_hw_payment_create,
        *_,
    ):
        mock_hw_payment_create.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "PayPal transfer method email address should be same as profile email address.",
                        "code": "CONSTRAINT_VIOLATIONS",
                    }
                ]
            }
        )
        self.assertTrue(self.serializer.is_valid())
        data = self.serializer.save()

        self.assertFalse(data['is_success'])
        self.assertTrue(data['cancel_revenue_payment'])
        mock_unlock_fn.called_once_with(self.user.pk)

    @mock.patch(
        "payouts.ffwd.validate_royalty_advance_offer",
        return_value={
            "royalty_advance_offer": {"split_ids_for_locking": [1]},
            "is_valid": True,
            "withdrawal_total": 1000.00,
            "royalty_advance_id": "12345678-1234-1234-1234-123456789123",
        },
    )
    @mock.patch('hyperwallet.Api.createPayment')
    def test_accept_ffwd_failed_and_not_canceled(
        self,
        mock_hw_payment_create,
        *_,
    ):
        mock_hw_payment_create.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "Connection reset by peer.",
                        "code": "COMMUNICATION_ERROR",
                    }
                ]
            }
        )
        self.assertTrue(self.serializer.is_valid())
        data = self.serializer.save()
        self.assertFalse(data['is_success'])
        self.assertFalse(data['cancel_revenue_payment'])
