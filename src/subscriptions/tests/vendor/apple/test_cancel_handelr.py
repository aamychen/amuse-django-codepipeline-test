from unittest.mock import patch
from rest_framework import status

from users.tests.factories import UserFactory
from subscriptions.vendor.apple.apple import AppleNotificationHandler
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory, PaymentMethodFactory
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from subscriptions.models import Subscription
from amuse.tests.test_api.base import AmuseAPITestCase

from .substring_matcher import SubstringMatcher
from .payloads_data import test_data_new_cancel, test_data_cancel_simple


class TestAppleCancelHandler(AmuseAPITestCase):
    def setUp(self):
        self.test_payload = {
            'latest_expired_receipt': 'a',
            'latest_expired_receipt_info': {
                'original_purchase_date_pst': '2021-01-12 15:10:39 America/Los_Angeles',
                'cancellation_date_ms': '1613675131000',
                'quantity': '1',
                'subscription_group_identifier': '20581044',
                'cancellation_reason': '0',
                'unique_vendor_identifier': '0B301BC7-DBD0-40C8-9BBD-EA032A530EBD',
                'original_purchase_date_ms': '1610493039000',
                'expires_date_formatted': '2021-03-14 12:59:44 Etc/GMT',
                'is_in_intro_offer_period': 'false',
                'purchase_date_ms': '1613311184000',
                'expires_date_formatted_pst': '2021-03-14 05:59:44 America/Los_Angeles',
                'is_trial_period': 'false',
                'item_id': '1491033244',
                'unique_identifier': '0a2397f6d47847d8af4bdb00fdf5de50cad11865',
                'original_transaction_id': '370000637905031',
                'expires_date': '1615726784000',
                'app_item_id': '1160922922',
                'transaction_id': '370000659681527',
                'in_app_ownership_type': 'PURCHASED',
                'bvrs': '2501',
                'web_order_line_item_id': '370000258307274',
                'version_external_identifier': '839645891',
                'bid': 'io.amuse.ios',
                'cancellation_date': '2021-02-18 19:05:31 Etc/GMT',
                'product_id': 'amuse_pro_monthly_renewal',
                'purchase_date': '2021-02-14 13:59:44 Etc/GMT',
                'cancellation_date_pst': '2021-02-18 11:05:31 America/Los_Angeles',
                'purchase_date_pst': '2021-02-14 05:59:44 America/Los_Angeles',
                'original_purchase_date': '2021-01-12 23:10:39 Etc/GMT',
            },
            'cancellation_date': '2021-02-18 19:05:31 Etc/GMT',
            'unified_receipt': {
                'latest_expired_receipt': 'a',
                'pending_renewal_info': [
                    {
                        'original_transaction_id': '370000637905031',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'auto_renew_status': '0',
                        'auto_renew_product_id': 'amuse_pro_monthly_renewal',
                    }
                ],
                'environment': 'Production',
                'status': 0,
                'latest_receipt_info': [
                    {
                        'cancellation_reason': '0',
                        'in_app_ownership_type': 'PURCHASED',
                        'expires_date': '2021-03-14 12:59:44 Etc/GMT',
                        'original_purchase_date_ms': '1610493039000',
                        'original_transaction_id': '370000637905031',
                        'subscription_group_identifier': '20581044',
                        'expires_date_ms': '1615726784000',
                        'quantity': '1',
                        'web_order_line_item_id': '370000258307274',
                        'purchase_date_ms': '1613311184000',
                        'cancellation_date_ms': '1613675131000',
                        'transaction_id': '370000659681527',
                        'purchase_date_pst': '2021-02-14 05:59:44 America/Los_Angeles',
                        'expires_date_pst': '2021-03-14 05:59:44 America/Los_Angeles',
                        'cancellation_date': '2021-02-18 19:05:31 Etc/GMT',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'purchase_date': '2021-02-14 13:59:44 Etc/GMT',
                        'original_purchase_date_pst': '2021-01-12 15:10:39 America/Los_Angeles',
                        'cancellation_date_pst': '2021-02-18 11:05:31 America/Los_Angeles',
                        'is_in_intro_offer_period': 'false',
                        'original_purchase_date': '2021-01-12 23:10:39 Etc/GMT',
                        'is_trial_period': 'false',
                    },
                    {
                        'expires_date_pst': '2021-02-12 15:10:37 America/Los_Angeles',
                        'purchase_date': '2021-01-12 23:10:37 Etc/GMT',
                        'in_app_ownership_type': 'PURCHASED',
                        'purchase_date_ms': '1610493037000',
                        'original_purchase_date_ms': '1610493039000',
                        'transaction_id': '370000637905031',
                        'original_transaction_id': '370000637905031',
                        'quantity': '1',
                        'expires_date_ms': '1613171437000',
                        'original_purchase_date_pst': '2021-01-12 15:10:39 America/Los_Angeles',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'subscription_group_identifier': '20581044',
                        'web_order_line_item_id': '370000258307273',
                        'expires_date': '2021-02-12 23:10:37 Etc/GMT',
                        'is_in_intro_offer_period': 'false',
                        'original_purchase_date': '2021-01-12 23:10:39 Etc/GMT',
                        'purchase_date_pst': '2021-01-12 15:10:37 America/Los_Angeles',
                        'is_trial_period': 'false',
                    },
                ],
            },
            'auto_renew_product_id': 'amuse_pro_monthly_renewal',
            'notification_type': 'CANCEL',
            'environment': 'PROD',
            'auto_renew_status': 'false',
            'bvrs': '2501',
            'web_order_line_item_id': '370000258307274',
            'cancellation_date_ms': '1613675131000',
            'cancellation_date_pst': '2021-02-18 11:05:31 America/Los_Angeles',
            'bid': 'io.amuse.ios',
        }
        self.user = UserFactory()
        self.payment_method = PaymentMethodFactory(
            external_recurring_id='370000637905031', method='AAPL', user=self.user
        )
        self.plan = self.plan = SubscriptionPlanFactory(
            apple_product_id='amuse_pro_monthly_renewal', trial_days=0
        )
        self.sub = SubscriptionFactory(plan=self.plan, user=self.user)
        self.payment = PaymentTransactionFactory(
            user=self.user,
            plan=self.plan,
            subscription=self.sub,
            external_transaction_id='370000637905031',
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
        tx = PaymentTransaction.objects.get(id=self.payment.id)
        sub = Subscription.objects.get(id=self.sub.id)
        self.assertEqual(tx.status, PaymentTransaction.STATUS_CANCELED)
        self.assertEqual(sub.status, Subscription.STATUS_EXPIRED)

    @patch('subscriptions.vendor.apple.cancel_handler.logger.warning')
    def test_original_transaction_not_found(self, mock_logger):
        result = self.handler.process_notification(test_data_new_cancel)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        mock_logger.assert_called_once_with(
            SubstringMatcher(containing='Probably INITIAL_BUY failed')
        )

    @patch('subscriptions.vendor.apple.cancel_handler.logger.warning')
    def test_compex_case_not_implemented(self, mock_logger):
        self.payment.external_transaction_id = '170000845146887'
        self.payment.save()
        result = self.handler.process_notification(test_data_new_cancel)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        mock_logger.assert_called_once_with(SubstringMatcher(containing='complex'))

    def test_simple_single_tx_in_payload(self):
        test_data_cancel_simple['unified_receipt']['latest_receipt_info'][0][
            'transaction_id'
        ] = '370000637905031'
        result = self.handler.process_notification(test_data_cancel_simple)
        print(result.content)
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        tx = PaymentTransaction.objects.get(id=self.payment.id)
        sub = Subscription.objects.get(id=self.sub.id)
        self.assertEqual(tx.status, PaymentTransaction.STATUS_CANCELED)
        self.assertEqual(sub.status, Subscription.STATUS_EXPIRED)
