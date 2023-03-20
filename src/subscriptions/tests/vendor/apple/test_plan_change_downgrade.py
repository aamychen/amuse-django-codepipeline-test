from unittest.mock import patch
from rest_framework import status

from users.tests.factories import UserFactory
from subscriptions.vendor.apple.apple import AppleNotificationHandler
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory, PaymentMethodFactory
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from subscriptions.models import Subscription, SubscriptionPlan
from amuse.tests.test_api.base import AmuseAPITestCase


class TestApplePlanChangeDowngradeHandler(AmuseAPITestCase):
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
                'latest_receipt': 'b',
                'pending_renewal_info': [
                    {
                        'original_transaction_id': '430000729594340',
                        'product_id': 'amuse_pro_monthly_renewal',
                        'auto_renew_status': '1',
                        'auto_renew_product_id': 'amuse_pro_monthly_renewal_notrials',
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
            'auto_renew_product_id': 'amuse_pro_monthly_renewal_notrials',
            'notification_type': 'DID_CHANGE_RENEWAL_PREF',
        }
        self.user = UserFactory()
        self.payment_method = PaymentMethodFactory(
            external_recurring_id='430000729594340', method='AAPL', user=self.user
        )
        self.plan = self.plan = SubscriptionPlanFactory(
            apple_product_id='amuse_pro_monthly_renewal',
            trial_days=0,
            tier=SubscriptionPlan.TIER_PRO,
        )
        self.new_plan = SubscriptionPlanFactory(
            apple_product_id='amuse_pro_monthly_renewal_notrials',
            tier=SubscriptionPlan.TIER_PRO,
        )
        self.sub = SubscriptionFactory(plan=self.plan, user=self.user)
        self.payment = PaymentTransactionFactory(
            user=self.user,
            plan=self.plan,
            subscription=self.sub,
            external_transaction_id='430000729594340',
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

    def test_valid_data_case_crossgrade(self):
        response = self.handler.process_notification(self.test_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sub = Subscription.objects.get(id=self.sub.id)
        self.assertEqual(sub.plan, self.new_plan)

    def test_valid_data_case_downgrade(self):
        self.new_plan.tier = SubscriptionPlan.TIER_PLUS
        self.new_plan.save()
        response = self.handler.process_notification(self.test_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sub = Subscription.objects.get(id=self.sub.id)
        self.assertEqual(sub.plan, self.plan)
