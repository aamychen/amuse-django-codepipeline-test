from unittest.mock import patch
import responses
from django.test import TestCase, override_settings
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
)
from amuse.tests.helpers import add_zendesk_mock_post_response
from payouts.tests.factories import PayeeFactory
from payouts.receipt import UserReceipts, get_last_payment_return_reason
from hyperwallet.models import Receipt


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestHyperwalletUserNotificationHander(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
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
                "token": "rcp-8b1b7cfd-ef3b-46dc-8ce7-ac3fe15b07d5",
                "journalId": "500232343",
                "type": "TRANSFER_TO_PAYPAL_ACCOUNT",
                "createdOn": "2021-10-07T07:55:58",
                "entry": "DEBIT",
                "sourceToken": "usr-0bd1c3f4-23b0-4f80-bd4c-d901db267a9e",
                "destinationToken": "trm-b9fd83af-3600-43db-9f53-c1946b560ff4",
                "amount": "44.71",
                "fee": "1.00",
                "currency": "USD",
                "details": {
                    "payeeName": "Koffi Sith",
                    "bankAccountId": "molemopedi1@gmail.com",
                },
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
                "token": "rcp-fd7683db-c6c6-4f1f-ae49-9548f8e8a7bf",
                "journalId": "500312863",
                "type": "PAYMENT_RETURN",
                "createdOn": "2021-10-07T11:09:27",
                "entry": "DEBIT",
                "sourceToken": "usr-0bd1c3f4-23b0-4f80-bd4c-d901db267a9e",
                "destinationToken": "act-7c79e775-4011-4b21-8b9e-2534c496fbe0",
                "amount": "43.71",
                "currency": "USD",
                "details": {"clientPaymentId": "430"},
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
            {
                "token": "rcp-49086b20-7c97-4a7e-b1f3-eb25f5960204",
                "journalId": "500317317",
                "type": "TRANSFER_TO_PAYPAL_ACCOUNT",
                "createdOn": "2021-10-07T11:21:49",
                "entry": "DEBIT",
                "sourceToken": "usr-0bd1c3f4-23b0-4f80-bd4c-d901db267a9e",
                "destinationToken": "trm-b9fd83af-3600-43db-9f53-c1946b560ff4",
                "amount": "43.71",
                "fee": "1.00",
                "currency": "USD",
                "details": {
                    "payeeName": "Koffi Sith",
                    "bankAccountId": "molemopedi1@gmail.com",
                },
            },
        ]
        self.payee = PayeeFactory()
        self.receipt_objects = [Receipt(data=d) for d in self.receipts]

    @patch("hyperwallet.Api.listReceiptsForUser")
    def test_get_last_payment_return_reason(self, mocked_fnc):
        mocked_fnc.return_value = self.receipt_objects
        user_receipts = UserReceipts(payee=self.payee)
        reason = user_receipts.get_last_transfer_return_reason()
        assert reason == "Account Does Not Exist"

    @patch("hyperwallet.Api.listReceiptsForUser")
    def test_get_last_payment_return_reason_helper_fnc(self, mocked_fnc):
        mocked_fnc.return_value = self.receipt_objects
        reason = get_last_payment_return_reason(payee=self.payee)
        assert reason == "Account Does Not Exist"
