from unittest.mock import patch
from rest_framework import status
from django.utils import timezone

from users.tests.factories import UserFactory
from subscriptions.vendor.apple.apple import AppleNotificationHandler
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory, PaymentMethodFactory
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from subscriptions.models import Subscription
from amuse.tests.test_api.base import AmuseAPITestCase
from .payloads_data import test_data_upgrade
from subscriptions.vendor.apple.commons import process_receipt_extended
from .substring_matcher import SubstringMatcher


class TestAppleInteractiveRenewHandler(AmuseAPITestCase):
    def setUp(self):
        self.test_payload = {
            'latest_receipt': 'a',
            'latest_receipt_info': {
                'original_purchase_date_pst': '2020-11-17 19:23:34 America/Los_Angeles',
                'quantity': '1',
                'subscription_group_identifier': '20581044',
                'unique_vendor_identifier': 'EC0C1741-86E6-4F1D-A10E-CA1591D91845',
                'original_purchase_date_ms': '1605669814000',
                'expires_date_formatted': '2021-03-18 03:47:02 Etc/GMT',
                'is_in_intro_offer_period': 'false',
                'purchase_date_ms': '1613623622000',
                'expires_date_formatted_pst': '2021-03-17 20:47:02 America/Los_Angeles',
                'is_trial_period': 'false',
                'item_id': '1491033244',
                'unique_identifier': '00008030-001C24C621DB802E',
                'original_transaction_id': '430000729594340',
                'expires_date': '1616039222000',
                'app_item_id': '1160922922',
                'transaction_id': '430000787887990',
                'in_app_ownership_type': 'PURCHASED',
                'bvrs': '2718',
                'web_order_line_item_id': '430000302577640',
                'version_external_identifier': '840349842',
                'bid': 'io.amuse.ios',
                'product_id': 'amuse_pro_monthly_renewal',
                'purchase_date': '2021-02-18 04:47:02 Etc/GMT',
                'purchase_date_pst': '2021-02-17 20:47:02 America/Los_Angeles',
                'original_purchase_date': '2020-11-18 03:23:34 Etc/GMT',
            },
            'environment': 'PROD',
            'auto_renew_status': 'true',
            'unified_receipt': {
                'latest_receipt': 'a',
                'pending_renewal_info': [
                    {
                        'original_transaction_id': '430000729594340',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'auto_renew_status': '1',
                        'auto_renew_product_id': 'amuse_pro_monthly_renewal',
                    }
                ],
                'environment': 'Production',
                'status': 0,
                'latest_receipt_info': [
                    {
                        'expires_date_pst': '2021-03-17 20:47:02 America/Los_Angeles',
                        'purchase_date': '2021-02-18 04:47:02 Etc/GMT',
                        'in_app_ownership_type': 'PURCHASED',
                        'purchase_date_ms': '1613623622000',
                        'original_purchase_date_ms': '1605669814000',
                        'transaction_id': '430000787887990',
                        'original_transaction_id': '430000729594340',
                        'quantity': '1',
                        'expires_date_ms': '1616039222000',
                        'original_purchase_date_pst': '2020-11-17 19:23:34 America/Los_Angeles',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'subscription_group_identifier': '20581044',
                        'web_order_line_item_id': '430000302577640',
                        'expires_date': '2021-03-18 03:47:02 Etc/GMT',
                        'is_in_intro_offer_period': 'false',
                        'original_purchase_date': '2020-11-18 03:23:34 Etc/GMT',
                        'purchase_date_pst': '2021-02-17 20:47:02 America/Los_Angeles',
                        'is_trial_period': 'false',
                    },
                    {
                        'expires_date_pst': '2021-01-17 19:23:32 America/Los_Angeles',
                        'purchase_date': '2020-12-18 03:23:32 Etc/GMT',
                        'in_app_ownership_type': 'PURCHASED',
                        'purchase_date_ms': '1608261812000',
                        'original_purchase_date_ms': '1605669814000',
                        'transaction_id': '430000745670487',
                        'original_transaction_id': '430000729594340',
                        'quantity': '1',
                        'expires_date_ms': '1610940212000',
                        'original_purchase_date_pst': '2020-11-17 19:23:34 America/Los_Angeles',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'subscription_group_identifier': '20581044',
                        'web_order_line_item_id': '430000293325421',
                        'expires_date': '2021-01-18 03:23:32 Etc/GMT',
                        'is_in_intro_offer_period': 'false',
                        'original_purchase_date': '2020-11-18 03:23:34 Etc/GMT',
                        'purchase_date_pst': '2020-12-17 19:23:32 America/Los_Angeles',
                        'is_trial_period': 'false',
                    },
                    {
                        'expires_date_pst': '2020-12-17 19:23:32 America/Los_Angeles',
                        'purchase_date': '2020-11-18 03:23:32 Etc/GMT',
                        'in_app_ownership_type': 'PURCHASED',
                        'purchase_date_ms': '1605669812000',
                        'original_purchase_date_ms': '1605669814000',
                        'transaction_id': '430000729594340',
                        'original_transaction_id': '430000729594340',
                        'quantity': '1',
                        'expires_date_ms': '1608261812000',
                        'original_purchase_date_pst': '2020-11-17 19:23:34 America/Los_Angeles',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'subscription_group_identifier': '20581044',
                        'web_order_line_item_id': '430000293325420',
                        'expires_date': '2020-12-18 03:23:32 Etc/GMT',
                        'is_in_intro_offer_period': 'false',
                        'original_purchase_date': '2020-11-18 03:23:34 Etc/GMT',
                        'purchase_date_pst': '2020-11-17 19:23:32 America/Los_Angeles',
                        'is_trial_period': 'false',
                    },
                ],
            },
            'bvrs': '2400',
            'bid': 'io.amuse.ios',
            'auto_renew_product_id': 'amuse_pro_monthly_renewal',
            'notification_type': 'INTERACTIVE_RENEWAL',
        }

        self.user = UserFactory()
        self.payment_method = PaymentMethodFactory(
            external_recurring_id='430000787887990', method='AAPL', user=self.user
        )
        self.plan = self.plan = SubscriptionPlanFactory(
            apple_product_id='amuse_pro_monthly_renewal', trial_days=0
        )
        self.sub = SubscriptionFactory(
            plan=self.plan, user=self.user, payment_method=self.payment_method
        )
        self.payment = PaymentTransactionFactory(
            user=self.user,
            plan=self.plan,
            subscription=self.sub,
            external_transaction_id='430000787887990',
            payment_method=self.payment_method,
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

    def test_valid_data_renew_tx_exist(self):
        self.sub.stats = Subscription.STATUS_EXPIRED
        self.sub.save()
        response = self.handler.process_notification(self.test_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        txs = PaymentTransaction.objects.filter(subscription=self.sub.id).order_by(
            '-created'
        )
        sub = Subscription.objects.get(id=self.sub.id)
        assert txs.count() == 1
        self.assertEqual(sub.status, Subscription.STATUS_ACTIVE)

    def test_valid_data_renew_tx_new_created(self):
        self.sub.stats = Subscription.STATUS_EXPIRED
        self.sub.save()
        self.payment.external_transaction_id = '430000729594340'
        self.payment.save()
        response = self.handler.process_notification(self.test_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        txs = PaymentTransaction.objects.filter(subscription=self.sub.id).order_by(
            '-created'
        )
        last_payment = txs.first()
        last_tx_from_payload = self.test_payload['unified_receipt'][
            'latest_receipt_info'
        ][0]
        last_tx_id_from_payload = last_tx_from_payload['transaction_id']
        sub = Subscription.objects.get(id=self.sub.id)
        assert txs.count() == 2

        self.assertEqual(sub.status, Subscription.STATUS_ACTIVE)
        self.assertEqual(last_tx_id_from_payload, last_payment.external_transaction_id)

    @patch('subscriptions.vendor.apple.interactive_renewal_handler.logger')
    def test_400_returned_if_no_tx_found(self, mock_logger):
        self.payment.external_transaction_id = "a"
        self.payment.save()
        response = self.handler.process_notification(self.test_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(mock_logger.warning.called)

    @patch('subscriptions.vendor.apple.interactive_renewal_handler.logger')
    def test_400_returned_if_plan_not_fond(self, mock_logger):
        self.test_payload['unified_receipt']['latest_receipt_info'][0][
            'product_id'
        ] = "fake_plan"
        response = self.handler.process_notification(self.test_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(mock_logger.warning.called)

    def _build_upgrade_case(self):
        details = process_receipt_extended(test_data_upgrade)
        plan = SubscriptionPlanFactory(
            apple_product_id=details['next_to_last_transaction']['product_id'],
            trial_days=0,
        )
        self.sub.plan = plan
        self.payment.plan = plan
        self.payment.external_transaction_id = details['next_to_last_transaction'][
            'transaction_id'
        ]

        self.sub.save()
        self.payment.save()

        assert (
            self.payment.external_transaction_id
            == details['next_to_last_transaction']['transaction_id']
        )
        assert (
            self.sub.plan.apple_product_id
            == details['next_to_last_transaction']['product_id']
        )

    def _build_upgrade_case_exist(self):
        details = process_receipt_extended(test_data_upgrade)
        plan = SubscriptionPlanFactory(
            apple_product_id=details['last_transaction']['product_id'], trial_days=0
        )
        self.sub.plan = plan
        self.payment.plan = plan
        self.payment.external_transaction_id = details['last_transaction'][
            'transaction_id'
        ]

        self.sub.save()
        self.payment.save()

        assert (
            self.payment.external_transaction_id
            == details['last_transaction']['transaction_id']
        )
        assert (
            self.sub.plan.apple_product_id == details['last_transaction']['product_id']
        )

    @patch('subscriptions.vendor.apple.interactive_renewal_handler.logger.info')
    def test_upgrade_case(self, mock_logger):
        self._build_upgrade_case()
        details = process_receipt_extended(test_data_upgrade)
        apple_last_tx = details['last_transaction']
        apple_next_to_last = details['next_to_last_transaction']
        response = self.handler.process_notification(test_data_upgrade)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        all_subs = Subscription.objects.filter(user=self.user).order_by('created')
        all_payments = PaymentTransaction.objects.filter(user=self.user).order_by(
            'created'
        )
        first_payment = all_payments.first()
        last_payment = all_payments.last()
        first_sub = all_subs.first()
        second_sub = all_subs.last()
        assert details.get('is_upgraded') == 'true'
        assert all_subs.count() == 2
        assert first_sub.status == Subscription.STATUS_EXPIRED
        assert first_sub.valid_until == timezone.now().date()
        assert second_sub.status == Subscription.STATUS_ACTIVE
        assert first_sub.plan.apple_product_id == apple_next_to_last['product_id']
        assert second_sub.plan.apple_product_id == apple_last_tx['product_id']

        # Assert payments are correct
        assert first_payment.paid_until.date() == timezone.now().date()
        assert first_payment.plan.apple_product_id == apple_next_to_last['product_id']
        assert last_payment.status == PaymentTransaction.STATUS_APPROVED
        assert last_payment.plan.apple_product_id == apple_last_tx['product_id']
        mock_logger.called_once_with(SubstringMatcher(containing='UPGRADED'))

    @patch('subscriptions.vendor.apple.interactive_renewal_handler.logger')
    def test_upgrade_case_double_notification(self, mock_logger):
        self._build_upgrade_case_exist()
        details = process_receipt_extended(test_data_upgrade)
        apple_last_tx = details['last_transaction']
        response = self.handler.process_notification(test_data_upgrade)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        all_subs = Subscription.objects.filter(user=self.user).order_by('created')
        all_payments = PaymentTransaction.objects.filter(user=self.user).order_by(
            'created'
        )
        first_payment = all_payments.first()
        first_sub = all_subs.first()
        assert details.get('is_upgraded') == 'true'
        assert all_subs.count() == 1
        assert first_sub.status == Subscription.STATUS_ACTIVE
        assert first_sub.plan.apple_product_id == apple_last_tx['product_id']

        # Assert payments are correct
        assert first_payment.status == PaymentTransaction.STATUS_APPROVED
        assert first_payment.plan.apple_product_id == apple_last_tx['product_id']
        mock_logger.called_once_with(SubstringMatcher(containing='already upgraded  '))
