from unittest.mock import patch
from rest_framework import status

from users.tests.factories import UserFactory
from subscriptions.vendor.apple.apple import AppleNotificationHandler
from payments.tests.factories import PaymentTransactionFactory, PaymentMethodFactory
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from amuse.tests.test_api.base import AmuseAPITestCase
from .substring_matcher import SubstringMatcher


class TestAppleInitialBuyeHandler(AmuseAPITestCase):
    def setUp(self):
        self.test_payload = {
            'latest_receipt': '',
            'latest_receipt_info': {
                'original_purchase_date_pst': '2021-02-18 12:41:52 America/Los_Angeles',
                'quantity': '1',
                'subscription_group_identifier': '20581044',
                'unique_vendor_identifier': '23FEEBD0-D692-42B5-A70E-6085DEE3B0F3',
                'original_purchase_date_ms': '1613680912000',
                'expires_date_formatted': '2021-03-18 19:41:51 Etc/GMT',
                'is_in_intro_offer_period': 'false',
                'purchase_date_ms': '1613680911000',
                'expires_date_formatted_pst': '2021-03-18 12:41:51 America/Los_Angeles',
                'is_trial_period': 'false',
                'item_id': '1491033244',
                'unique_identifier': '00008101-000419591E89003A',
                'original_transaction_id': '280000788232996',
                'expires_date': '1616096511000',
                'app_item_id': '1160922922',
                'transaction_id': '280000788232996',
                'in_app_ownership_type': 'PURCHASED',
                'bvrs': '2775',
                'web_order_line_item_id': '280000318728195',
                'version_external_identifier': '840520254',
                'bid': 'io.amuse.ios',
                'product_id': 'amuse_pro_monthly_renewal',
                'purchase_date': '2021-02-18 20:41:51 Etc/GMT',
                'purchase_date_pst': '2021-02-18 12:41:51 America/Los_Angeles',
                'original_purchase_date': '2021-02-18 20:41:52 Etc/GMT',
            },
            'environment': 'PROD',
            'auto_renew_status': 'true',
            'unified_receipt': {
                'latest_receipt': '',
                'pending_renewal_info': [
                    {
                        'original_transaction_id': '280000788232996',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'auto_renew_status': '1',
                        'auto_renew_product_id': 'amuse_pro_monthly_renewal',
                    }
                ],
                'environment': 'Production',
                'status': 0,
                'latest_receipt_info': [
                    {
                        'expires_date_pst': '2021-03-18 12:41:51 America/Los_Angeles',
                        'purchase_date': '2021-02-18 20:41:51 Etc/GMT',
                        'in_app_ownership_type': 'PURCHASED',
                        'purchase_date_ms': '1613680911000',
                        'original_purchase_date_ms': '1613680912000',
                        'transaction_id': '280000788232996',
                        'original_transaction_id': '280000788232996',
                        'quantity': '1',
                        'expires_date_ms': '1616096511000',
                        'original_purchase_date_pst': '2021-02-18 12:41:52 America/Los_Angeles',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'subscription_group_identifier': '20581044',
                        'web_order_line_item_id': '280000318728195',
                        'expires_date': '2021-03-18 19:41:51 Etc/GMT',
                        'is_in_intro_offer_period': 'false',
                        'original_purchase_date': '2021-02-18 20:41:52 Etc/GMT',
                        'purchase_date_pst': '2021-02-18 12:41:51 America/Los_Angeles',
                        'is_trial_period': 'false',
                    }
                ],
            },
            'bvrs': '2775',
            'bid': 'io.amuse.ios',
            'auto_renew_product_id': 'amuse_pro_monthly_renewal',
            'notification_type': 'INITIAL_BUY',
        }
        # self.test_payload = payloads.initial_buy_payload

        self.user = UserFactory()
        self.payment_method = PaymentMethodFactory(
            external_recurring_id='280000788232996', method='AAPL', user=self.user
        )
        self.plan = self.plan = SubscriptionPlanFactory(
            apple_product_id='amuse_pro_monthly_renewal', trial_days=0
        )
        self.sub = SubscriptionFactory(plan=self.plan, user=self.user)
        self.payment = PaymentTransactionFactory(
            user=self.user,
            plan=self.plan,
            subscription=self.sub,
            external_transaction_id='280000788232996',
        )
        self.user = self.payment.user
        self.handler = AppleNotificationHandler()

    def test_payload_validator(self):
        is_valid = self.handler.is_payload_valid(self.test_payload)
        assert is_valid == True
        invalid_data = self.test_payload
        del invalid_data['unified_receipt']
        not_valid = self.handler.is_payload_valid(invalid_data)
        assert not_valid == False

    def test_valid_data_case(self):
        response = self.handler.process_notification(self.test_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_corrupted_payload(self):
        new_payload = self.test_payload
        del new_payload['notification_type']
        result = self.handler.process_notification(new_payload)
        self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('subscriptions.vendor.apple.apple.logger.warning')
    def test_no_handeler_implemeted(self, mock_logger):
        new_payload = self.test_payload
        new_payload['notification_type'] = 'NOT_IMPLEMENTED'
        result = self.handler.process_notification(new_payload)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        mock_logger.called_once_with(SubstringMatcher(containing='not implemented'))

    def test_can_not_find_tx_in_db(self):
        self.payment.external_transaction_id = 'a'
        self.payment.save()
        result = self.handler.process_notification(self.test_payload)
        self.assertEqual(result.status_code, status.HTTP_404_NOT_FOUND)
