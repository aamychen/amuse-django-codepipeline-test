import json
from unittest.mock import patch

import responses
from django.test import override_settings, TransactionTestCase
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
)

from amuse.tests.helpers import add_zendesk_mock_post_response
from payouts.notifications.hw_payment_notification_handler import (
    HWPaymentNotificationHandler,
)
from payouts.tests.factories import PaymentFactory
from payouts.models import Event, Payment
from amuse.vendor.revenue.client import (
    URL_UPDATE_HYPERWALLET_WITHDRAWAL,
    URL_RECORD_HYPERWALLET_REFUND,
)
from hyperwallet.models import Receipt
from hyperwallet.exceptions import HyperwalletAPIException


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestHyperwalletPaymetNotificationHander(TransactionTestCase):
    reset_sequences = True

    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.pmt = PaymentFactory(
            external_id='pmt-0243d732-59bf-4898-9a34-384b0a2f48f3',
            status="CREATED",
            payment_type=Payment.TYPE_ROYALTY,
        )

        self.payload = {
            "token": "wbh-4af65f06-6b6e-41da-8091-7db872f180e7",
            "type": "PAYMENTS.UPDATED.STATUS.COMPLETED",
            "createdOn": "2021-07-15T16:44:05.995",
            "object": {
                "token": "pmt-0243d732-59bf-4898-9a34-384b0a2f48f3",
                "status": "COMPLETED",
                "createdOn": "2021-07-15T16:44:02",
                "amount": "3000.00",
                "currency": "EUR",
                "clientPaymentId": str(self.pmt.pk),
                "purpose": "OTHER",
                "expiresOn": "2022-01-11T16:44:02",
                "destinationToken": "trm-242e3dc5-1e95-4bab-a6ce-fe412942a6b2",
                "programToken": "prg-2157a14c-6c0c-4a5e-83d9-6b6911453af8",
            },
        }

        self.refund_payload = {
            "token": "wbh-4af65f06-6b6e-41da-8091-7db872f180e7",
            "type": "PAYMENTS.UPDATED.STATUS.RETURNED",
            "createdOn": "2021-07-15T16:44:05.995",
            "object": {
                "token": "pmt-0243d732-59bf-4898-9a34-384b0a2f48f3",
                "status": "RETURNED",
                "createdOn": "2021-07-15T16:44:02",
                "amount": "1500.00",
                "currency": "EUR",
                "clientPaymentId": "1",
                "purpose": "OTHER",
                "expiresOn": "2022-01-11T16:44:02",
                "destinationToken": "trm-242e3dc5-1e95-4bab-a6ce-fe412942a6b2",
                "programToken": "prg-2157a14c-6c0c-4a5e-83d9-6b6911453af8",
            },
        }

        self.receipts = [
            {
                "token": "rcp-754b1781-c00e-4a4a-9f1f-3375a04e4f94",
                "journalId": "500232322",
                "type": "PAYMENT",
                "createdOn": "2021-10-07T07:55:58",
                "entry": "CREDIT",
                "sourceToken": "act-7c79e775-4011-4b21-8b9e-2534c496fbe0",
                "destinationToken": "usr-0bd1c3f4-23b0-4f80-bd4c-d901db267a9e",
                "amount": "44.71",
                "currency": "USD",
                "details": {"clientPaymentId": "430", "payeeName": "Koffi Sith"},
            },
            {
                "token": "rcp-d6db4428-e03e-4285-be98-1cd7e156a46c",
                "journalId": "500312862",
                "type": "PAYPAL_ACCOUNT_TRANSFER_RETURN",
                "createdOn": "2021-10-07T11:09:27",
                "entry": "CREDIT",
                "sourceToken": "trm-b9fd83af-3600-43db-9f53-c1946b560ff4",
                "destinationToken": "usr-0bd1c3f4-23b0-4f80-bd4c-d901db267a9e",
                "amount": "43.71",
                "currency": "USD",
                "details": {
                    "returnOrRecallReason": "Account Does Not Exist",
                    "payeeName": "Koffi Sith",
                    "bankAccountId": "molemopedi1@gmail.com",
                },
            },
            {
                "token": "rcp-c0d62f88-cabd-4895-be61-dc274bf511c8",
                "journalId": "500317316",
                "type": "PAYMENT",
                "createdOn": "2021-10-07T11:21:49",
                "entry": "CREDIT",
                "sourceToken": "act-7c79e775-4011-4b21-8b9e-2534c496fbe0",
                "destinationToken": "usr-0bd1c3f4-23b0-4f80-bd4c-d901db267a9e",
                "amount": "43.71",
                "currency": "USD",
                "details": {"clientPaymentId": "440", "payeeName": "Koffi Sith"},
            },
        ]
        self.receipt_objects = [Receipt(data=d) for d in self.receipts]

    @responses.activate
    def test_success_case_royalty(self):
        response = {"transaction_id": "6e570b62-7f8d-41ee-8b99-e611d9f3626d"}
        responses.add(
            responses.PUT,
            URL_UPDATE_HYPERWALLET_WITHDRAWAL,
            json.dumps(response),
            status=200,
        )

        handler = HWPaymentNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.pmt.refresh_from_db()
        self.assertTrue(status['is_success'])
        self.assertEqual(self.pmt.status, self.payload['object']['status'])
        # Assert event is recoded in Event table
        event = Event.objects.get(
            object_id=self.payload['object']['token'],
        )
        self.assertEqual(event.reason, "HW notification")
        self.assertEqual(event.payload, self.payload)

    @responses.activate
    @patch("hyperwallet.Api.listReceiptsForUser")
    @patch(
        'payouts.notifications.hw_payment_notification_handler.HWPaymentNotificationHandler._send_event'
    )
    def test_refund_case(self, mock_send, mocked_hw_api):
        mocked_hw_api.return_value = self.receipt_objects
        response = {"transaction_id": "6e570b62-7f8d-41ee-8b99-e611d9f3626d"}
        responses.add(
            responses.POST,
            URL_RECORD_HYPERWALLET_REFUND,
            json.dumps(response),
            status=201,
        )

        handler = HWPaymentNotificationHandler(payload=self.refund_payload)
        status = handler.handle()
        self.pmt.refresh_from_db()
        self.assertTrue(status['is_success'])
        self.assertEqual(self.pmt.status, self.refund_payload['object']['status'])
        # Assert event is recoded in Event table
        event = Event.objects.get(
            object_id=self.refund_payload['object']['token'],
        )
        self.assertEqual(event.reason, "HW notification")
        self.assertEqual(event.payload, self.refund_payload)
        mock_send.assert_called_with(payment=self.pmt)

    def test_ignore_CREATED_notification(self):
        self.payload['object']['status'] = "CREATED"
        handler = HWPaymentNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.assertEqual(status['is_success'], True)

    def test_no_payment_found(self):
        self.payload['object']['clientPaymentId'] = "1000001"
        handler = HWPaymentNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.assertEqual(status['is_success'], False)

    @patch('payouts.notifications.hw_payment_notification_handler.logger.info')
    def test_new_status_not_allowed(self, mocked_log):
        self.pmt.status = "COMPLETED"
        self.pmt.save()
        self.payload['object']['status'] = "IN_PROGRESS"
        handler = HWPaymentNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.assertEqual(status['is_success'], True)
        self.pmt.refresh_from_db()
        self.assertEqual(self.pmt.status, "COMPLETED")
        self.assertEqual(mocked_log.call_count, 2)

    @responses.activate
    @patch("hyperwallet.Api.listReceiptsForUser")
    @patch('payouts.notifications.hw_payment_notification_handler.logger.info')
    def test_send_event(self, mocked_log, mocked_hw_api):
        mocked_hw_api.return_value = self.receipt_objects

        handler = HWPaymentNotificationHandler(payload=self.refund_payload)
        handler._parse_payload()
        handler._send_event(payment=self.pmt)
        self.assertEqual(mocked_log.call_count, 1)

    @responses.activate
    @patch("hyperwallet.Api.listReceiptsForUser")
    @patch('payouts.notifications.hw_payment_notification_handler.logger.info')
    def test_send_event_exception(self, mocked_log, mocked_hw_api):
        mocked_hw_api.side_effect = HyperwalletAPIException(
            {
                "errors": [
                    {
                        "message": "Error messaage",
                        "fieldName": "clientUserId",
                        "code": "ERROR_CODE",
                        "relatedResources": [
                            "usr-3c0840da-fbf4-464d-9bcb-a16018de66b7"
                        ],
                    }
                ]
            }
        )

        handler = HWPaymentNotificationHandler(payload=self.refund_payload)
        handler._parse_payload()
        with self.assertRaises(Exception) as context:
            handler._send_event(payment=None)
        self.assertTrue("object has no attribute" in str(context.exception))

    @patch('payouts.notifications.hw_payment_notification_handler.logger.info')
    def test_new_status_not_allowed_after_RETURNED(self, mocked_log):
        self.pmt.status = "RETURNED"
        self.pmt.save()
        self.payload['object']['status'] = "COMPLETED"
        handler = HWPaymentNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.assertEqual(status['is_success'], True)
        self.pmt.refresh_from_db()
        self.assertEqual(self.pmt.status, "RETURNED")
        self.assertEqual(mocked_log.call_count, 2)

    @patch('payouts.notifications.hw_payment_notification_handler.logger.info')
    def test_premature_notification_case(self, mocked_log):
        self.pmt.external_id = "pmt-init"
        self.pmt.save()
        self.payload['object']['status'] = "COMPLETED"
        handler = HWPaymentNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.assertEqual(status['is_success'], False)
        self.pmt.refresh_from_db()
        self.assertEqual(self.pmt.status, "CREATED")
        self.assertEqual(mocked_log.call_count, 2)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestHyperwalletPaymetNotificationAdvance(TransactionTestCase):
    reset_sequences = True

    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.pmt = PaymentFactory(
            external_id='pmt-0243d732-59bf-4898-9a34-384b0a2f48f4',
            status="CREATED",
            payment_type=Payment.TYPE_ADVANCE,
        )
        self.payload = {
            "token": "wbh-4af65f06-6b6e-41da-8091-7db872f180e7",
            "type": "PAYMENTS.UPDATED.STATUS.COMPLETED",
            "createdOn": "2021-07-15T16:44:05.995",
            "object": {
                "token": "pmt-0243d732-59bf-4898-9a34-384b0a2f48f4",
                "status": "COMPLETED",
                "createdOn": "2021-07-15T16:44:02",
                "amount": "3000.00",
                "currency": "EUR",
                "clientPaymentId": str(self.pmt.pk),
                "purpose": "OTHER",
                "expiresOn": "2022-01-11T16:44:02",
                "destinationToken": "trm-242e3dc5-1e95-4bab-a6ce-fe412942a6b2",
                "programToken": "prg-2157a14c-6c0c-4a5e-83d9-6b6911453af8",
            },
        }

        self.refund_payload = {
            "token": "wbh-4af65f06-6b6e-41da-8091-7db872f180e7",
            "type": "PAYMENTS.UPDATED.STATUS.RETURNED",
            "createdOn": "2021-07-15T16:44:05.995",
            "object": {
                "token": "pmt-0243d732-59bf-4898-9a34-384b0a2f48f4",
                "status": "RETURNED",
                "createdOn": "2021-07-15T16:44:02",
                "amount": "1500.00",
                "currency": "EUR",
                "clientPaymentId": "2",
                "purpose": "OTHER",
                "expiresOn": "2022-01-11T16:44:02",
                "destinationToken": "trm-242e3dc5-1e95-4bab-a6ce-fe412942a6b2",
                "programToken": "prg-2157a14c-6c0c-4a5e-83d9-6b6911453af8",
            },
        }

    @patch(
        "payouts.notifications.hw_payment_notification_handler.update_royalty_advance_offer",
        return_value={"advance_id": "12345678-1234-1234-1234-123456789123"},
    )
    def test_completed_case_advance(self, _):
        # set paymnet_type to advance
        self.pmt.paymet_type = Payment.TYPE_ADVANCE
        self.pmt.save()
        handler = HWPaymentNotificationHandler(payload=self.payload)
        status = handler.handle()
        self.pmt.refresh_from_db()
        self.assertTrue(status['is_success'])
        self.assertEqual(self.pmt.status, self.payload['object']['status'])
        self.assertEqual(self.pmt.paymet_type, Payment.TYPE_ADVANCE)
        # Assert event is recoded in Event table
        event = Event.objects.get(
            object_id=self.payload['object']['token'],
        )
        self.assertEqual(event.reason, "HW notification")
        self.assertEqual(event.payload, self.payload)

    @patch(
        "payouts.notifications.hw_payment_notification_handler.update_royalty_advance_offer",
        return_value={"advance_id": "12345678-1234-1234-1234-123456789123"},
    )
    @patch('payouts.ffwd.FFWDHelpers.unlock_splits')
    def test_cancel_case_advance(self, mock_unlock_fn, _):
        # mock out call to slayer to cancel offer
        payload = self.payload
        payload['object']['status'] = 'FAILED'

        handler = HWPaymentNotificationHandler(payload=payload)
        status = handler.handle()
        self.pmt.refresh_from_db()
        self.assertTrue(status['is_success'])
        self.assertEqual(self.pmt.status, self.payload['object']['status'])
        # Assert event is recoded in Event table
        event = Event.objects.get(
            object_id=self.payload['object']['token'],
        )
        self.assertEqual(event.reason, "HW notification")
        self.assertEqual(event.payload, self.payload)
        mock_unlock_fn.called_once_with(self.pmt.payee.pk)

    @responses.activate
    @patch('payouts.ffwd.FFWDHelpers.unlock_splits')
    @patch(
        "payouts.notifications.hw_payment_notification_handler.refund_royalty_advance_offer"
    )
    def test_return_case_advance(self, mock_slayer_refund, mock_unlock_fn):
        # TODO Add compete test once is completed
        # mock out call to slayer to refund offer
        payload = self.payload
        payload['object']['status'] = 'RETURNED'

        handler = HWPaymentNotificationHandler(payload=payload)
        status = handler.handle()
        self.pmt.refresh_from_db()
        self.assertTrue(status['is_success'])
        self.assertEqual(self.pmt.status, self.payload['object']['status'])
        # Assert event is recoded in Event table
        event = Event.objects.get(
            object_id=self.payload['object']['token'],
        )
        self.assertEqual(event.reason, "HW notification")
        self.assertEqual(event.payload, self.payload)
        mock_unlock_fn.called_once_with(self.pmt.payee.pk)
        mock_slayer_refund.called_once_with(
            user_id=self.pmt.payee.user.pk,
            royalty_advance_id=self.pmt.revenue_system_id,
            refund_amount_currency="USD",
            refund_amount=self.payload['object']['amount'],
            description=f"Hyperwallet return {self.payload['object']['token']}",
            refund_reference=self.pmt.pk,
        )

    @responses.activate
    def test_in_progress_case_advance(self):
        payload = self.payload
        payload['object']['status'] = 'IN_PROGRESS'

        handler = HWPaymentNotificationHandler(payload=payload)
        status = handler.handle()
        self.pmt.refresh_from_db()
        self.assertTrue(status['is_success'])
        self.assertEqual(self.pmt.status, "CREATED")
