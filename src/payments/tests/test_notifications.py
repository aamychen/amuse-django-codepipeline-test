from unittest.mock import patch
from datetime import date

import responses
from payments.models import PaymentTransaction
from payments.tests.factories import PaymentTransactionFactory
from subscriptions.models import Subscription
from payments.notifications.adyen import AdyenNoificationsHandler, HandleAUTHORISATION
from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.adyen.helpers import get_or_create_payment_method


class SubstringMatcher:
    def __init__(self, containing):
        self.containing = containing.lower()

    def __eq__(self, other):
        return other.lower().find(self.containing) > -1

    def __unicode__(self):
        return 'a string containing "%s"' % self.containing

    def __str__(self):
        return self.unicode().encode('utf-8')

    __repr__ = __unicode__


class AdyenAUTHORIZATIONHandler(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        self.payment = PaymentTransactionFactory()
        self.user = self.payment.user
        self.test_payload_card = {
            "live": "true",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "additionalData": {
                            "issuerCountry": "CO",
                            "expiryDate": "12/2012",
                            "cardBin": "409355",
                            "cardSummary": "0190",
                            "cardHolderName": "maria paz",
                            "recurringProcessingModel": "Subscription",
                            "visaTemplate": "InitialSubscription",
                        },
                        "amount": {"currency": "USD", "value": 1999},
                        "eventCode": "AUTHORISATION",
                        "eventDate": "2020-12-14T23:20:06+01:00",
                        "merchantAccountCode": "AmuseioABECOM",
                        "merchantReference": str(self.payment.id),
                        "paymentMethod": "visa",
                        "pspReference": "4736079844042463",
                        "reason": "null",
                        "success": "true",
                    }
                }
            ],
        }
        self.test_payload_paypal = {
            "live": "true",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "additionalData": {
                            "issuerCountry": "IN",
                            "recurring.shopperReference": "1004045",
                            "recurring.recurringDetailReference": "5916080333261084",
                        },
                        "amount": {"currency": "USD", "value": 1999},
                        "eventCode": "AUTHORISATION",
                        "eventDate": "2020-12-15T12:55:41+01:00",
                        "merchantAccountCode": "AmuseioABECOM",
                        "merchantReference": str(self.payment.id),
                        "operations": ["REFUND"],
                        "paymentMethod": "paypal",
                        "pspReference": "4656080332803743",
                        "reason": "null",
                        "success": "true",
                    }
                }
            ],
        }
        self.test_payload_pay_method_change = {
            "live": "true",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "additionalData": {
                            "cardIssuingCurrency": "752",
                            "authCode": "807110",
                            "cardSummary": "5924",
                            "cardHolderName": "Checkout Shopper PlaceHolder",
                            "cardIssuingBank": "NORDEA BANK ABP",
                            "visaTemplate": "InitialCardOnFile",
                            "issuerCountry": "SE",
                            "expiryDate": "09\\/2021",
                            "cardBin": "453903",
                            "recurring.recurringDetailReference": "5916083046459060",
                            "recurringProcessingModel": "CardOnFile",
                            "recurring.shopperReference": "124555",
                            "cardPaymentMethod": "visastandarddebit",
                            "fundingSource": "DEBIT",
                            "cardIssuingCountry": "SE",
                        },
                        "amount": {"currency": "USD", "value": 0},
                        "eventCode": "AUTHORISATION",
                        "eventDate": "2020-12-18T16:17:24+01:00",
                        "merchantAccountCode": "AmuseioABECOM",
                        "merchantReference": "124555-AUTH-2020-12-18T15:17:24.258121+00:00",
                        "operations": ["CANCEL", "CAPTURE", "REFUND"],
                        "paymentMethod": "amex",
                        "pspReference": "4626083046442375",
                        "reason": "807110:5924:09\\/2021",
                        "success": "true",
                    }
                }
            ],
        }

        self.notification_hanlder = AdyenNoificationsHandler()

    def test_create_or_update_payment_method(self):
        notification_data_card = self.test_payload_card['notificationItems'][0][
            'NotificationRequestItem'
        ]
        notification_data_paypal = self.test_payload_paypal['notificationItems'][0][
            'NotificationRequestItem'
        ]
        notification_data_method_change = self.test_payload_pay_method_change[
            'notificationItems'
        ][0]['NotificationRequestItem']

        pm_object = get_or_create_payment_method(self.user, notification_data_card)
        self.assertEqual(pm_object.external_recurring_id, None)

        pm_object2 = get_or_create_payment_method(self.user, notification_data_paypal)
        self.assertEqual(pm_object2.external_recurring_id, '5916080333261084')

        pm_object3 = get_or_create_payment_method(
            self.user, notification_data_method_change
        )
        self.assertEqual(pm_object3.external_recurring_id, '5916083046459060')

    def test_get_recurring_detail_reference(self):
        handler = HandleAUTHORISATION()
        notification_data_card = self.test_payload_card['notificationItems'][0][
            'NotificationRequestItem'
        ]
        notification_data_paypal = self.test_payload_paypal['notificationItems'][0][
            'NotificationRequestItem'
        ]
        notification_data_method_change = self.test_payload_pay_method_change[
            'notificationItems'
        ][0]['NotificationRequestItem']

        test1 = handler._get_recurring_detail_reference(notification_data_card)
        assert test1 is None
        test2 = handler._get_recurring_detail_reference(notification_data_paypal)
        assert test2 == "5916080333261084"
        test3 = handler._get_recurring_detail_reference(notification_data_method_change)
        assert test3 == "5916083046459060"

    def _corrupt_data_db(self):
        self.payment.status = PaymentTransaction.STATUS_ERROR
        self.payment.subscription.status = Subscription.STATUS_CREATED
        self.payment.payment_method = None
        self.payment.save()
        self.payment.subscription.save()

    def _set_grace_period_case(self):
        self.payment.status = PaymentTransaction.STATUS_ERROR
        self.payment.subscription.status = Subscription.STATUS_GRACE_PERIOD
        self.payment.subscription.valid_until = date(2020, 1, 1)
        self.payment.payment_method = None
        self.payment.save()
        self.payment.subscription.save()

    def test_no_handler(self):
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'eventCode'
        ] = 'NOHANLDER'
        status = self.notification_hanlder.process_notification(self.test_payload_card)
        assert status == True

    def test_AUTHORISATION_sucess_fix_data_card(self):
        self._corrupt_data_db()
        status = self.notification_hanlder.process_notification(self.test_payload_card)
        assert status == True
        tx = PaymentTransaction.objects.get(pk=self.payment.pk)
        sub = tx.subscription

        # Assert transaction data is fixed
        self.assertEqual(tx.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(
            tx.external_transaction_id,
            self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
                'pspReference'
            ],
        )
        self.assertEqual(
            tx.external_payment_response, 'Succesful AUTHORISATION notification'
        )

        # Assert subscription data is fixed
        self.assertEqual(sub.status, Subscription.STATUS_ACTIVE)

        # Assert payment method data is fixed
        payment_method = tx.payment_method
        self.assertIsNotNone(payment_method)
        self.assertEqual(payment_method.method, 'visa')

    def test_AUTHORISATION_sucess_fix_data_paypal(self):
        self._corrupt_data_db()
        status = self.notification_hanlder.process_notification(
            self.test_payload_paypal
        )
        assert status == True
        tx = PaymentTransaction.objects.get(pk=self.payment.pk)
        sub = tx.subscription

        # Assert transaction data is fixed
        self.assertEqual(tx.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(
            tx.external_transaction_id,
            self.test_payload_paypal['notificationItems'][0]['NotificationRequestItem'][
                'pspReference'
            ],
        )
        self.assertEqual(
            tx.external_payment_response, 'Succesful AUTHORISATION notification'
        )

        # Assert subscription data is fixed
        self.assertEqual(sub.status, Subscription.STATUS_ACTIVE)

        # Assert payment method data is fixed
        payment_method = tx.payment_method
        self.assertIsNotNone(payment_method)
        self.assertEqual(payment_method.method, 'paypal')
        self.assertEqual(payment_method.external_recurring_id, "5916080333261084")

    def test_data_is_not_changed_for_correct_states_success(self):
        status = self.notification_hanlder.process_notification(self.test_payload_card)
        assert status == True
        tx = PaymentTransaction.objects.get(pk=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_APPROVED)
        self.assertNotEqual(
            tx.external_payment_response, 'Succesful AUTHORISATION notification'
        )
        self.assertEqual(sub.status, Subscription.STATUS_ACTIVE)

    def test_data_is_not_changed_for_correct_states_failed(self):
        self._corrupt_data_db()
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'success'
        ] = 'false'

        status = self.notification_hanlder.process_notification(self.test_payload_card)
        assert status == True
        tx = PaymentTransaction.objects.get(pk=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(sub.status, Subscription.STATUS_ERROR)

    def test_AUTHORISATION_failed_fix_data(self):
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'success'
        ] = 'false'
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'reason'
        ] = 'ERROR'

        status = self.notification_hanlder.process_notification(self.test_payload_card)
        assert status == True
        tx = PaymentTransaction.objects.get(pk=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(tx.external_payment_response, 'ERROR')
        self.assertEqual(sub.status, Subscription.STATUS_ERROR)

    def test_AUTHORISATION_failed_GP_expired(self):
        self._set_grace_period_case()
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'success'
        ] = 'false'
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'reason'
        ] = 'ERROR'
        status = self.notification_hanlder.process_notification(self.test_payload_card)
        assert status == True
        tx = PaymentTransaction.objects.get(pk=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(sub.status, Subscription.STATUS_EXPIRED)

    @patch('payments.notifications.adyen.logger.info')
    def test_AUTHORISATION_failed_with_approved_tx_in_history(self, mock_logger):
        PaymentTransactionFactory(
            subscription=self.payment.subscription,
            amount=10,
            type=PaymentTransaction.TYPE_PAYMENT,
        )
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'success'
        ] = 'false'
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'reason'
        ] = 'ERROR'
        status = self.notification_hanlder.process_notification(self.test_payload_card)
        assert status == True
        tx = PaymentTransaction.objects.get(pk=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(sub.status, Subscription.STATUS_EXPIRED)
        self.assertTrue(mock_logger.called)

    @patch('payments.notifications.adyen.logger.info')
    def test_AUTHORISATION_failed_with_approved_tx_in_history_direct(self, mock_logger):
        from payments.notifications.adyen import HandleAUTHORISATION

        PaymentTransactionFactory(
            subscription=self.payment.subscription,
            amount=10,
            type=PaymentTransaction.TYPE_PAYMENT,
        )
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'success'
        ] = 'false'
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'reason'
        ] = 'ERROR'
        HandleAUTHORISATION().handle(
            self.test_payload_card['notificationItems'][0]['NotificationRequestItem']
        )
        tx = PaymentTransaction.objects.get(pk=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(sub.status, Subscription.STATUS_EXPIRED)
        mock_logger.assert_called_with(
            SubstringMatcher(containing='sub_status=EXPIRED')
        )

    def test_success_AUTHORISATION_payment_method_change_notification(self):
        self.payment.external_transaction_id = "4626083046442375"
        self.payment.save()
        p_method = self.test_payload_pay_method_change['notificationItems'][0][
            'NotificationRequestItem'
        ]['paymentMethod']

        p_summary = self.test_payload_pay_method_change['notificationItems'][0][
            'NotificationRequestItem'
        ]['additionalData']['cardSummary']

        status = self.notification_hanlder.process_notification(
            self.test_payload_pay_method_change
        )
        assert status == True
        tx = PaymentTransaction.objects.get(pk=self.payment.pk)
        self.assertEqual(tx.payment_method.method, p_method)
        self.assertEqual(tx.payment_method.summary, p_summary)
        self.assertEqual(tx.user, tx.payment_method.user)

    def test_failed_AUTHORISATION_payment_method_change_notification(self):
        self.test_payload_pay_method_change['notificationItems'][0][
            'NotificationRequestItem'
        ]['success'] = 'false'
        status = self.notification_hanlder.process_notification(
            self.test_payload_pay_method_change
        )
        assert status == True
        tx = PaymentTransaction.objects.get(pk=self.payment.pk)
        self.assertEqual(tx.payment_method.method, self.payment.payment_method.method)
        self.assertEqual(tx.payment_method.summary, self.payment.payment_method.summary)

    @patch('payments.notifications.adyen.logger.warning')
    def test_payment_method_change_tx_not_found(self, mock_logger):
        status = self.notification_hanlder.process_notification(
            self.test_payload_pay_method_change
        )
        assert status == True
        mock_logger.assert_called_once_with(
            SubstringMatcher(containing='Can not find tx')
        )

    @patch('payments.notifications.adyen.logger.warning')
    def test_panic_message_on_exception(self, mock_logger):
        self.test_payload_card['notificationItems'][0]['NotificationRequestItem'][
            'merchantReference'
        ] = '11111111'  # No existing transaction in DB

        status = self.notification_hanlder.process_notification(self.test_payload_card)
        assert status == False
        mock_logger.assert_called_once_with(SubstringMatcher(containing='PANIC'))


class TestDisputeHandlers(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        self.payment = PaymentTransactionFactory()
        self.user = self.payment.user
        self.test_payload_chargeback = {
            "live": "true",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "additionalData": {
                            "chargebackReasonCode": "10.4",
                            "chargebackSchemeCode": "visa",
                            "arn": "74987500310000298697653",
                            "ed": "4-0353  2021865205F1",
                        },
                        "amount": {"currency": "EUR", "value": 659},
                        "eventCode": "CHARGEBACK",
                        "eventDate": "2020-12-21T09:00:39+01:00",
                        "merchantAccountCode": "AmuseioABECOM",
                        "merchantReference": str(self.payment.pk),
                        "originalReference": "1759045706843171",
                        "paymentMethod": "visa",
                        "pspReference": "7559082222661042",
                        "reason": "Other Fraud-Card Absent Environment",
                        "success": "true",
                    }
                }
            ],
        }
        self.test_payload_chargeback_reversed = {
            "live": "true",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "additionalData": {"arn": "74987500307000188027651"},
                        "amount": {"currency": "EUR", "value": 675},
                        "eventCode": "CHARGEBACK_REVERSED",
                        "eventDate": "2020-12-07T09:59:47+01:00",
                        "merchantAccountCode": "AmuseioABECOM",
                        "merchantReference": str(self.payment.pk),
                        "paymentMethod": "visa",
                        "pspReference": "1659043114025250",
                        "reason": "Cancelled Recurring",
                        "success": "true",
                    }
                }
            ],
        }
        self.test_payload_second_chargeback = {
            "live": "true",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "additionalData": {
                            "chargebackReasonCode": "13.7",
                            "chargebackSchemeCode": "visa",
                            "arn": "74987500173000132927353",
                            "ed": "7-0217  1956822931F1",
                        },
                        "amount": {"currency": "EUR", "value": 683},
                        "eventCode": "SECOND_CHARGEBACK",
                        "eventDate": "2020-10-09T09:12:34+02:00",
                        "merchantAccountCode": "AmuseioABECOM",
                        "merchantReference": str(self.payment.pk),
                        "paymentMethod": "visa",
                        "pspReference": "1855927336518716",
                        "reason": "Cancelled Merchandise\\/Services",
                        "success": "true",
                    }
                }
            ],
        }

        self.notification_hanlder = AdyenNoificationsHandler()

    def test_sucess_CHARGEBACK(self):
        status = self.notification_hanlder.process_notification(
            self.test_payload_chargeback
        )
        assert status == True
        tx = PaymentTransaction.objects.get(id=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(sub.status, Subscription.STATUS_EXPIRED)

    def test_success_CHARGEBACK_REVERSED(self):
        self.payment.status = PaymentTransaction.STATUS_ERROR
        self.payment.subscription.status = Subscription.STATUS_EXPIRED
        self.payment.save()
        self.payment.subscription.save()

        self.assertEqual(self.payment.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(self.payment.subscription.status, Subscription.STATUS_EXPIRED)

        status = self.notification_hanlder.process_notification(
            self.test_payload_chargeback_reversed
        )
        assert status == True
        tx = PaymentTransaction.objects.get(id=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(sub.status, Subscription.STATUS_ACTIVE)

    def test_success_SECOND_CHARGEBACK(self):
        status = self.notification_hanlder.process_notification(
            self.test_payload_second_chargeback
        )
        assert status == True
        tx = PaymentTransaction.objects.get(id=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(sub.status, Subscription.STATUS_EXPIRED)


class TestFraudHandlers(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        self.payment = PaymentTransactionFactory()
        self.user = self.payment.user
        self.test_payload_fraud = {
            "live": "true",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "additionalData": {
                            "nofReasonCode": "06",
                            "arn": "15265670349313892976833",
                            "nofSchemeCode": "mc",
                        },
                        "amount": {"currency": "USD", "value": 1999},
                        "eventCode": "NOTIFICATION_OF_FRAUD",
                        "eventDate": "2020-12-27T22:03:10+01:00",
                        "merchantAccountCode": "AmuseioABECOM",
                        "merchantReference": str(self.payment.pk),
                        "originalReference": "1739079655400704",
                        "paymentMethod": "mc",
                        "pspReference": "7436090764780624",
                        "reason": "Card Not Present Fraud",
                        "success": "true",
                    }
                }
            ],
        }
        self.notification_hanlder = AdyenNoificationsHandler()

    def test_success_fraud_notification(self):
        status = self.notification_hanlder.process_notification(self.test_payload_fraud)
        assert status == True
        tx = PaymentTransaction.objects.get(id=self.payment.pk)
        sub = tx.subscription
        user = sub.user
        self.assertEqual(tx.status, PaymentTransaction.STATUS_ERROR)
        self.assertEqual(sub.status, Subscription.STATUS_EXPIRED)


class TestRefundHandler(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        self.payment = PaymentTransactionFactory(
            external_transaction_id="883611671943365G"
        )
        self.test_payload_refund = {
            "live": "false",
            "notificationItems": [
                {
                    "NotificationRequestItem": {
                        "amount": {"currency": "USD", "value": 2000},
                        "eventCode": "REFUND",
                        "eventDate": "2021-04-17T21:00:27+02:00",
                        "merchantAccountCode": "AMUSEIOSTAGING",
                        "merchantReference": str(self.payment.pk),
                        "originalReference": "883611671943365G",
                        "paymentMethod": "amex",
                        "pspReference": "863618686025330E",
                        "reason": "",
                        "success": "true",
                    }
                }
            ],
        }
        self.notification_hanlder = AdyenNoificationsHandler()

    def test_success_refund_notification(self):
        status = self.notification_hanlder.process_notification(
            self.test_payload_refund
        )
        assert status == True
        tx = PaymentTransaction.objects.get(id=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_CANCELED)
        self.assertEqual(sub.status, Subscription.STATUS_EXPIRED)

    @patch('payments.notifications.adyen.logger.warning')
    def test_refund_failed_notificcation(self, mock_logger):
        self.test_payload_refund['notificationItems'][0]['NotificationRequestItem'][
            'success'
        ] = "false"
        status = self.notification_hanlder.process_notification(
            self.test_payload_refund
        )
        assert status == True
        tx = PaymentTransaction.objects.get(id=self.payment.pk)
        sub = tx.subscription
        self.assertEqual(tx.status, PaymentTransaction.STATUS_APPROVED)
        self.assertEqual(sub.status, Subscription.STATUS_ACTIVE)
        mock_logger.assert_called_once_with(
            SubstringMatcher(containing='adyen FAILED to refund')
        )
