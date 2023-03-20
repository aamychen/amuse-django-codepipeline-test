from unittest.mock import patch
from unittest import skip
from rest_framework import status

from users.tests.factories import UserFactory
from subscriptions.vendor.apple.apple import AppleNotificationHandler
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory, PaymentMethodFactory
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from subscriptions.models import Subscription
from amuse.tests.test_api.base import AmuseAPITestCase
from .substring_matcher import SubstringMatcher
from .payloads_data import test_data_did_recover


class TestAppleRenewHandler(AmuseAPITestCase):
    def setUp(self):
        self.test_payload = {
            'notification_type': 'DID_RENEW',
            'environment': 'PROD',
            'auto_renew_product_id': 'amuse_pro_monthly_renewal',
            'auto_renew_status': 'true',
            'latest_receipt': '"',
            'latest_receipt_info': {
                'subscription_group_identifier': '20581044',
                'is_trial_period': 'false',
                'is_in_intro_offer_period': 'false',
                'unique_identifier': '2b3dbb7b4f9c4a1aeb6204b8a333c7e55b5967e5',
                'unique_vendor_identifier': '39F1725F-74BB-4FE9-81F9-A0417F238F0A',
                'web_order_line_item_id': '580000243244451',
                'expires_date': '1616102898000',
                'expires_date_formatted': '2021-03-18 21:28:18 Etc/GMT',
                'expires_date_formatted_pst': '2021-03-18 14:28:18 America/Los_Angeles',
                'purchase_date': '2021-02-18 22:28:18 Etc/GMT',
                'purchase_date_ms': '1613687298000',
                'purchase_date_pst': '2021-02-18 14:28:18 America/Los_Angeles',
                'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                'original_purchase_date_ms': '1589002388000',
                'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                'item_id': '1491033244',
                'app_item_id': '1160922922',
                'version_external_identifier': '835833364',
                'bid': 'io.amuse.ios',
                'product_id': 'amuse_pro_monthly_renewal',
                'transaction_id': '580000620928077',
                'original_transaction_id': '580000475569886',
                'quantity': '1',
                'bvrs': '1865',
                'in_app_ownership_type': 'PURCHASED',
            },
            'unified_receipt': {
                'status': 0,
                'environment': 'Production',
                'latest_receipt_info': [
                    {
                        'quantity': '1',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'transaction_id': '580000620928077',
                        'purchase_date': '2021-02-18 22:28:18 Etc/GMT',
                        'purchase_date_ms': '1613687298000',
                        'purchase_date_pst': '2021-02-18 14:28:18 America/Los_Angeles',
                        'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                        'original_purchase_date_ms': '1589002388000',
                        'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                        'expires_date': '2021-03-18 21:28:18 Etc/GMT',
                        'expires_date_ms': '1616102898000',
                        'expires_date_pst': '2021-03-18 14:28:18 America/Los_Angeles',
                        'web_order_line_item_id': '580000243244451',
                        'is_trial_period': 'false',
                        'is_in_intro_offer_period': 'false',
                        'original_transaction_id': '580000475569886',
                        'in_app_ownership_type': 'PURCHASED',
                        'subscription_group_identifier': '20581044',
                    },
                    {
                        'quantity': '1',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'transaction_id': '580000601133428',
                        'purchase_date': '2021-01-18 22:28:18 Etc/GMT',
                        'purchase_date_ms': '1611008898000',
                        'purchase_date_pst': '2021-01-18 14:28:18 America/Los_Angeles',
                        'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                        'original_purchase_date_ms': '1589002388000',
                        'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                        'expires_date': '2021-02-18 22:28:18 Etc/GMT',
                        'expires_date_ms': '1613687298000',
                        'expires_date_pst': '2021-02-18 14:28:18 America/Los_Angeles',
                        'web_order_line_item_id': '580000234562084',
                        'is_trial_period': 'false',
                        'is_in_intro_offer_period': 'false',
                        'original_transaction_id': '580000475569886',
                        'in_app_ownership_type': 'PURCHASED',
                        'subscription_group_identifier': '20581044',
                    },
                    {
                        'quantity': '1',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'transaction_id': '580000582880876',
                        'purchase_date': '2020-12-18 22:28:18 Etc/GMT',
                        'purchase_date_ms': '1608330498000',
                        'purchase_date_pst': '2020-12-18 14:28:18 America/Los_Angeles',
                        'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                        'original_purchase_date_ms': '1589002388000',
                        'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                        'expires_date': '2021-01-18 22:28:18 Etc/GMT',
                        'expires_date_ms': '1611008898000',
                        'expires_date_pst': '2021-01-18 14:28:18 America/Los_Angeles',
                        'web_order_line_item_id': '580000225151275',
                        'is_trial_period': 'false',
                        'is_in_intro_offer_period': 'false',
                        'original_transaction_id': '580000475569886',
                        'in_app_ownership_type': 'PURCHASED',
                        'subscription_group_identifier': '20581044',
                    },
                    {
                        'quantity': '1',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'transaction_id': '580000566008857',
                        'purchase_date': '2020-11-15 01:56:58 Etc/GMT',
                        'purchase_date_ms': '1605405418000',
                        'purchase_date_pst': '2020-11-14 17:56:58 America/Los_Angeles',
                        'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                        'original_purchase_date_ms': '1589002388000',
                        'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                        'expires_date': '2020-12-15 01:56:58 Etc/GMT',
                        'expires_date_ms': '1607997418000',
                        'expires_date_pst': '2020-12-14 17:56:58 America/Los_Angeles',
                        'web_order_line_item_id': '580000216978167',
                        'is_trial_period': 'false',
                        'is_in_intro_offer_period': 'false',
                        'original_transaction_id': '580000475569886',
                        'in_app_ownership_type': 'PURCHASED',
                        'subscription_group_identifier': '20581044',
                    },
                    {
                        'quantity': '1',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'transaction_id': '580000551103400',
                        'purchase_date': '2020-10-15 00:56:58 Etc/GMT',
                        'purchase_date_ms': '1602723418000',
                        'purchase_date_pst': '2020-10-14 17:56:58 America/Los_Angeles',
                        'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                        'original_purchase_date_ms': '1589002388000',
                        'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                        'expires_date': '2020-11-15 01:56:58 Etc/GMT',
                        'expires_date_ms': '1605405418000',
                        'expires_date_pst': '2020-11-14 17:56:58 America/Los_Angeles',
                        'web_order_line_item_id': '580000209019905',
                        'is_trial_period': 'false',
                        'is_in_intro_offer_period': 'false',
                        'original_transaction_id': '580000475569886',
                        'in_app_ownership_type': 'PURCHASED',
                        'subscription_group_identifier': '20581044',
                    },
                    {
                        'quantity': '1',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'transaction_id': '580000536612329',
                        'purchase_date': '2020-09-15 00:56:58 Etc/GMT',
                        'purchase_date_ms': '1600131418000',
                        'purchase_date_pst': '2020-09-14 17:56:58 America/Los_Angeles',
                        'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                        'original_purchase_date_ms': '1589002388000',
                        'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                        'expires_date': '2020-10-15 00:56:58 Etc/GMT',
                        'expires_date_ms': '1602723418000',
                        'expires_date_pst': '2020-10-14 17:56:58 America/Los_Angeles',
                        'web_order_line_item_id': '580000200960981',
                        'is_trial_period': 'false',
                        'is_in_intro_offer_period': 'false',
                        'original_transaction_id': '580000475569886',
                        'in_app_ownership_type': 'PURCHASED',
                        'subscription_group_identifier': '20581044',
                    },
                    {
                        'quantity': '1',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'transaction_id': '580000521499935',
                        'purchase_date': '2020-08-14 23:21:23 Etc/GMT',
                        'purchase_date_ms': '1597447283000',
                        'purchase_date_pst': '2020-08-14 16:21:23 America/Los_Angeles',
                        'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                        'original_purchase_date_ms': '1589002388000',
                        'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                        'expires_date': '2020-09-14 23:21:23 Etc/GMT',
                        'expires_date_ms': '1600125683000',
                        'expires_date_pst': '2020-09-14 16:21:23 America/Los_Angeles',
                        'web_order_line_item_id': '580000191467481',
                        'is_trial_period': 'false',
                        'is_in_intro_offer_period': 'false',
                        'original_transaction_id': '580000475569886',
                        'in_app_ownership_type': 'PURCHASED',
                        'subscription_group_identifier': '20581044',
                    },
                    {
                        'quantity': '1',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'transaction_id': '580000503170290',
                        'purchase_date': '2020-07-09 05:33:06 Etc/GMT',
                        'purchase_date_ms': '1594272786000',
                        'purchase_date_pst': '2020-07-08 22:33:06 America/Los_Angeles',
                        'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                        'original_purchase_date_ms': '1589002388000',
                        'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                        'expires_date': '2020-08-09 05:33:06 Etc/GMT',
                        'expires_date_ms': '1596951186000',
                        'expires_date_pst': '2020-08-08 22:33:06 America/Los_Angeles',
                        'web_order_line_item_id': '580000183925352',
                        'is_trial_period': 'false',
                        'is_in_intro_offer_period': 'false',
                        'original_transaction_id': '580000475569886',
                        'in_app_ownership_type': 'PURCHASED',
                        'subscription_group_identifier': '20581044',
                    },
                    {
                        'quantity': '1',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'transaction_id': '580000489489179',
                        'purchase_date': '2020-06-09 05:33:06 Etc/GMT',
                        'purchase_date_ms': '1591680786000',
                        'purchase_date_pst': '2020-06-08 22:33:06 America/Los_Angeles',
                        'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                        'original_purchase_date_ms': '1589002388000',
                        'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                        'expires_date': '2020-07-09 05:33:06 Etc/GMT',
                        'expires_date_ms': '1594272786000',
                        'expires_date_pst': '2020-07-08 22:33:06 America/Los_Angeles',
                        'web_order_line_item_id': '580000176526486',
                        'is_trial_period': 'false',
                        'is_in_intro_offer_period': 'false',
                        'original_transaction_id': '580000475569886',
                        'in_app_ownership_type': 'PURCHASED',
                        'subscription_group_identifier': '20581044',
                    },
                    {
                        'quantity': '1',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'transaction_id': '580000475569886',
                        'purchase_date': '2020-05-09 05:33:06 Etc/GMT',
                        'purchase_date_ms': '1589002386000',
                        'purchase_date_pst': '2020-05-08 22:33:06 America/Los_Angeles',
                        'original_purchase_date': '2020-05-09 05:33:08 Etc/GMT',
                        'original_purchase_date_ms': '1589002388000',
                        'original_purchase_date_pst': '2020-05-08 22:33:08 America/Los_Angeles',
                        'expires_date': '2020-06-09 05:33:06 Etc/GMT',
                        'expires_date_ms': '1591680786000',
                        'expires_date_pst': '2020-06-08 22:33:06 America/Los_Angeles',
                        'web_order_line_item_id': '580000176526485',
                        'is_trial_period': 'false',
                        'is_in_intro_offer_period': 'false',
                        'original_transaction_id': '580000475569886',
                        'in_app_ownership_type': 'PURCHASED',
                        'subscription_group_identifier': '20581044',
                    },
                ],
                'latest_receipt': "a",
                'pending_renewal_info': [
                    {
                        'auto_renew_status': '1',
                        'auto_renew_product_id': 'amuse_pro_monthly_renewal',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'original_transaction_id': '580000475569886',
                    }
                ],
            },
            'bid': 'io.amuse.ios',
            'bvrs': '1865',
        }

        self.user = UserFactory()
        self.payment_method = PaymentMethodFactory(
            external_recurring_id='580000475569886', method='AAPL', user=self.user
        )
        self.plan = self.plan = SubscriptionPlanFactory(
            apple_product_id='amuse_pro_monthly_renewal', trial_days=0
        )
        self.sub = SubscriptionFactory(plan=self.plan, user=self.user)
        self.payment = PaymentTransactionFactory(
            user=self.user,
            plan=self.plan,
            subscription=self.sub,
            external_transaction_id='580000475569886',
        )
        self.user = self.payment.user
        self.handler = AppleNotificationHandler()

    @patch(
        'amuse.vendor.apple.subscriptions.AppleReceiptValidationAPIClient.validate_simple',
        return_value=True,
    )
    def test_apple_receipt_validation(self, mock_method):
        status = self.handler.is_receipt_valid(self.test_payload)
        assert status == True

    def test_payload_validator(self):
        is_valid = self.handler.is_payload_valid(self.test_payload)
        assert is_valid == True
        invalid_data = self.test_payload
        del invalid_data['unified_receipt']
        not_valid = self.handler.is_payload_valid(invalid_data)
        assert not_valid == False

    def test_valid_data_did_renew(self):
        response = self.handler.process_notification(self.test_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        txs = PaymentTransaction.objects.filter(subscription=self.sub.id).order_by(
            '-created'
        )
        assert txs.count() == 2

    def test_valid_data_did_recover(self):
        self.sub.status = Subscription.STATUS_EXPIRED
        self.sub.save()
        response = self.handler.process_notification(test_data_did_recover)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        txs = PaymentTransaction.objects.filter(subscription=self.sub.id).order_by(
            '-created'
        )
        assert txs.count() == 2
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.status == Subscription.STATUS_ACTIVE)

    @patch('subscriptions.vendor.apple.renew_handler.logger')
    def test_400_returned_on_exception(self, mock_logger):
        self.payment.external_transaction_id = 'a'
        self.payment.save()

        response = self.handler.process_notification(self.test_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(mock_logger.warning.called)

    @patch('subscriptions.vendor.apple.renew_handler.logger')
    def test_fail_to_renew_in_retry_period(self, mock_logger):
        from .payloads_data import test_data_did_fail_to_renew

        payload = test_data_did_fail_to_renew
        self.payment.external_transaction_id = '30000911451712'
        self.payment.save()
        response = self.handler.process_notification(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.valid_until, self.payment.paid_until.date())
        self.assertEqual(self.sub.status, Subscription.STATUS_ACTIVE)
        self.assertTrue(
            mock_logger.info.called_with(SubstringMatcher(containing='retry period'))
        )
        self.assertTrue(mock_logger.warning.not_called)

    @patch('subscriptions.vendor.apple.renew_handler.logger')
    def test_fail_to_renew_expired(self, mock_logger):
        from .payloads_data import test_data_did_fail_to_renew2

        self.payment.external_transaction_id = '30000911451712'
        self.payment.save()
        response = self.handler.process_notification(test_data_did_fail_to_renew2)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.valid_until, self.payment.paid_until.date())
        self.assertEqual(self.sub.status, Subscription.STATUS_EXPIRED)
        self.assertTrue(
            mock_logger.info.called_with(SubstringMatcher(containing='expired'))
        )
        self.assertTrue(mock_logger.warning.not_called)

    @patch('subscriptions.vendor.apple.renew_handler.logger')
    def test_double_did_renew_notification_case(self, mock_logger):
        # Simulate tx already exist
        PaymentTransactionFactory(
            external_transaction_id='580000620928077',
            subscription=self.sub,
            user=self.user,
        )
        self.sub.status = Subscription.STATUS_EXPIRED
        self.sub.save()
        response = self.handler.process_notification(self.test_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        txs = PaymentTransaction.objects.filter(subscription=self.sub.id).order_by(
            '-created'
        )
        assert txs.count() == 2
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.status == Subscription.STATUS_ACTIVE)
        self.assertTrue(mock_logger.warning.not_called)
        self.assertTrue(mock_logger.info.not_called)
