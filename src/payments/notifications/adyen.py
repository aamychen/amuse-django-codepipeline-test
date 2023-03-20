from uuid import uuid4
from django.utils import timezone
from amuse.logging import logger
from payments.models import PaymentTransaction
from subscriptions.models import Subscription
from amuse.vendor.adyen.helpers import get_or_create_payment_method
from subscriptions.rules import Action, ChangeReason


LOG_MESSAGE_TX_FAILED = (
    'Adyen notification handler txid= {0} Failed {1}, '
    'updating transaction: transaction_id={2} status=ERROR,'
    'reason={3} pspRef={4}'
)
LOG_MESSAGE_TX_SUCESS = (
    'Adyen notification handler txid= {0} Success {1}, '
    'updating transaction: transaction_id={2} status=APPROVED,'
    'reason=success pspRef={3}'
)
LOG_MESSAGE_SUB_SUCESS = (
    'Adyen notification handler txid= {0} Success {1}, '
    'updating subscription: transaction_id={2} status=APPROVED,'
    'reason=success pspRef={3}, subscription_id={4} sub_status=ACTIVE'
)
LOG_MESSAGE_SUB_FAILED = (
    'Adyen notification handler txid= {0} Failed {1}, '
    'updating subscription: transaction_id={2} status=ERROR,'
    'reason={3} pspRef={4}, subscription_id={5} sub_status=ERROR'
)
LOG_MESSAGE_SUB_FAILED_GP = (
    'Adyen notification handler txid= {0} Failed {1}, '
    'updating subscription: transaction_id={2} status=ERROR,'
    'reason={3} pspRef={4}, subscription_id={5} sub_status=EXPIRED'
)


class HandleRefundNotification(object):
    """
    REFUND notification
    payment -> canceled
    sub -> expired, if this last valid transaction
    """

    def __init__(self):
        self.id = uuid4()
        self.notification_name = 'REFUND'

    def _cancel_payment(self, transaction):
        transaction.status = PaymentTransaction.STATUS_CANCELED
        transaction.paid_until = timezone.now()
        transaction.save()
        logger.info(
            f'Adyen txid {self.id} {self.notification_name} payment {transaction.id} CANCELED'
        )

    def _expire_subscription(self, subscription):
        Action.expire(
            subscription=subscription,
            valid_until=timezone.now().date(),
            change_reason=ChangeReason.ADYEN_CANCELED,
        )
        logger.info(
            f'Adyen txid {self.id} {self.notification_name} subscription {subscription.id} EXPIRED'
        )

    def handle(self, notification_data):
        try:
            transaction_id = notification_data['merchantReference']
            transaction = PaymentTransaction.objects.get(pk=transaction_id)
            subscription = transaction.subscription
            success = notification_data['success']
            if success != 'true':
                psp_ref = notification_data["originalReference"]
                logger.warning(
                    f'Adyen txid {self.id} {self.notification_name} psp_ref {psp_ref} adyen FAILED to refund'
                )
                return True
            self._cancel_payment(transaction)
            self._expire_subscription(subscription)
            return True
        except Exception as e:
            logger.warning(
                f'Adyen txid {self.id} {self.notification_name} {notification_data} FAILED to refund error={e}'
            )


class HandleFraudNotification(object):
    """
    Implementation of MONEY-36
    NOTIFICATION_OF_FRAUD
    transaction -> ERROR
    sub -> EXPIRE
    user -> freeze
    """

    def __init__(self):
        self.id = uuid4()
        self.fraud_handlers = {'NOTIFICATION_OF_FRAUD': self.handle_fraud_notification}

    def handle(self, notification_data):
        try:
            transaction_id = notification_data['merchantReference']
            event = notification_data['eventCode']
            transaction = PaymentTransaction.objects.get(pk=transaction_id)
            subscription = transaction.subscription
            handler = self.fraud_handlers.get(event)
            handler(transaction, subscription, notification_data)
            return True
        except Exception as e:
            logger.warning(
                f'PANIC!. Unable to collect basic data for processing for: {notification_data} error {e} '
            )
            return False

    def handle_fraud_notification(self, transaction, subscription, notification_data):
        success = notification_data['success']
        if success != 'true':
            logger.info(
                f"Fraud handler txid={self.id} failed NOTIFICATION_OF_FRAUD : {notification_data}"
            )
            return
        transaction.status = PaymentTransaction.STATUS_ERROR
        transaction.external_payment_response = notification_data['reason']
        transaction.save()
        logger.info(
            f"Success NOTIFICATION_OF_FRAUD txid={self.id} transaction {transaction.id} set to ERROR."
        )
        user = subscription.user
        user.flag_for_fraud()
        subscription.status = Subscription.STATUS_EXPIRED
        subscription.save()
        logger.info(
            f"Success NOTIFICATION_OF_FRAUD txid={self.id} subscription {subscription.id} set to EXPIRED. User {user.id} flagged."
        )


class HandleDisputeNotifications(object):
    """
    Implementation of MONEY-36
    """

    def __init__(self):
        self.id = uuid4()
        self.dispute_handlers = {
            'CHARGEBACK': self.handle_chargeback,
            'CHARGEBACK_REVERSED': self.handle_chargeback_reversed,
            'SECOND_CHARGEBACK': self.handle_chargeback,
        }

    def tx_related_to_active_sub(self, transaction):
        """
        Determine is disputed transaction attached to current active subscription
        """
        tx_paid_until = transaction.paid_until
        subscription = transaction.subscription
        return subscription is not None and tx_paid_until > timezone.now()

    def handle(self, notification_data):
        try:
            transaction_id = notification_data['merchantReference']
            event = notification_data['eventCode']
            transaction = PaymentTransaction.objects.get(pk=transaction_id)
            subscription = transaction.subscription
            handler = self.dispute_handlers.get(event)
            handler(transaction, subscription, notification_data)
            return True
        except Exception as e:
            logger.warning(
                f'PANIC!. Unable to collect basic data for processing for: {notification_data} error {e} '
            )
            return False

    def handle_chargeback(self, transaction, subscription, notification_data):
        """
        On successfull CHARGEBACK set tx to ERROR and sub to ERRROR
        """
        success = notification_data['success']
        if success != 'true':
            logger.info(
                f"Dispute handler txid={self.id} failed CHARGEBACK: {notification_data}"
            )
            return
        transaction.status = PaymentTransaction.STATUS_ERROR
        transaction.external_payment_response = notification_data['reason']
        transaction.save()
        logger.info(
            f"Success CHARGEBACK txid={self.id} transaction {transaction.id} set to ERROR."
        )
        if self.tx_related_to_active_sub(transaction):
            subscription.status = Subscription.STATUS_EXPIRED
            subscription.save()
            logger.info(
                f"Success CHARGEBACK txid={self.id} subscription {subscription.id} expired."
            )

    def handle_chargeback_reversed(self, transaction, subscription, notification_data):
        success = notification_data['success']
        if success != 'true':
            logger.info(
                f"Dispute handler txid={self.id} failed CHARGEBACK_REVERSED: {notification_data}"
            )
            return
        transaction.status = PaymentTransaction.STATUS_APPROVED
        transaction.external_payment_response = notification_data['reason']
        transaction.save()
        logger.info(
            f"Success CHARGEBACK_REVERSED txid={self.id} transaction {transaction.id} set to APPROVED."
        )
        if self.tx_related_to_active_sub(transaction):
            subscription.status = Subscription.STATUS_ACTIVE
            subscription.save()
            logger.info(
                f"Success CHARGEBACK_REVERSED txid={self.id} subscription {subscription.id} activated ."
            )


class HandleAUTHORISATION(object):
    """
    Handling AUTHORISATION notification.
    Update transaction  and subscription  details according to status
    Log any data discrepancy found in the process
    In case of duplicates use the details contained in the latest notification

    Possible Subscription state transitions:
    ACTIVE->ERROR
    CREATED -> ACTIVE
    CREATED -> ERROR
    GRACE_PERIOD -> ACTIVE
    GRACE_PERIOD -> ERROR
    """

    def __init__(self):
        self.id = uuid4()
        self.notification_name = 'AUTHORISATION'

    def _get_auth_notification_type(self, notification_data):
        """
        AUTHORISATION notification can be send for transaction and for changing payment
        method. This two cases are handled differently.
        :param notification_data:
        :return:
        """
        n_type = 'tx'
        m_reference = notification_data['merchantReference']
        if 'AUTH' in m_reference and '-' in m_reference:
            n_type = 'auth'
        return n_type

    def _get_recurring_detail_reference(self, notification_data):
        additional_data = notification_data['additionalData']
        return additional_data.get('recurring.recurringDetailReference')

    def _confirm_or_update_payment_method(self, notification_data):
        success = notification_data['success']
        if success != 'true':
            return
        psp_ref = notification_data['pspReference']
        transaction = PaymentTransaction.objects.filter(
            external_transaction_id=psp_ref
        ).first()
        if not transaction:
            logger.warning(
                f'Adyen notification handler txid= {self.id} unable to update payment method. Can not find tx. {notification_data}'
            )
            return
        subscription = transaction.subscription
        payment_method = get_or_create_payment_method(
            subscription.user, notification_data
        )
        transaction.payment_method = payment_method
        subscription.payment_method = transaction.payment_method
        transaction.save()
        subscription.save()
        logger.info(
            f'Adyen notification handler txid= {self.id} Success {self.notification_name} updated payment_method_id={payment_method.pk}'
        )

    def _have_approved_tx_in_history(self, subscription):
        txs = PaymentTransaction.objects.filter(
            subscription=subscription,
            status=PaymentTransaction.STATUS_APPROVED,
            amount__gt=0,
            type=PaymentTransaction.TYPE_PAYMENT,
        )
        if not txs:
            return False
        return True

    def _confirm_or_update_on_failed_tx(
        self, transaction, subscription, notification_data
    ):
        """
        Validate states for failed transaction and update data if needed
        TODO Move payment and subscription updating code to custom state manger class
        """
        if transaction.status != PaymentTransaction.STATUS_ERROR:
            transaction.status = PaymentTransaction.STATUS_ERROR
            transaction.external_payment_response = notification_data['reason']
            transaction.external_transaction_id = notification_data['pspReference']
            transaction.save()
            tx_log_message = LOG_MESSAGE_TX_FAILED.format(
                self.id,
                self.notification_name,
                transaction.pk,
                notification_data['reason'],
                notification_data['pspReference'],
            )
            logger.info(tx_log_message)

        if subscription.status == Subscription.STATUS_GRACE_PERIOD:
            grace_period_until = subscription.allowed_grace_period_until()
            today = timezone.now().date()
            if grace_period_until <= today:
                subscription.status = Subscription.STATUS_EXPIRED
                subscription.save()
                sub_log_message = LOG_MESSAGE_SUB_FAILED_GP.format(
                    self.id,
                    self.notification_name,
                    transaction.pk,
                    notification_data['reason'],
                    notification_data['pspReference'],
                    subscription.pk,
                )
                logger.info(sub_log_message)
            return

        if not self._have_approved_tx_in_history(subscription):
            subscription.status = Subscription.STATUS_ERROR
            subscription.valid_until = subscription.paid_until
            subscription.save()
            sub_log_message = LOG_MESSAGE_SUB_FAILED.format(
                self.id,
                self.notification_name,
                transaction.pk,
                notification_data['reason'],
                notification_data['pspReference'],
                subscription.pk,
            )
            logger.info(sub_log_message)
            return

        if subscription.status != Subscription.STATUS_EXPIRED:
            subscription.status = Subscription.STATUS_EXPIRED
            subscription.valid_until = subscription.paid_until
            subscription.save()
            sub_log_message = LOG_MESSAGE_SUB_FAILED_GP.format(
                self.id,
                self.notification_name,
                transaction.pk,
                notification_data['reason'],
                notification_data['pspReference'],
                subscription.pk,
            )
            logger.info(sub_log_message)

    def _confirm_or_update_on_success_tx(
        self, transaction, subscription, notification_data
    ):
        """
        Validate states for successful transaction and update data if needed
        """
        if transaction.status != PaymentTransaction.STATUS_APPROVED:
            transaction.status = PaymentTransaction.STATUS_APPROVED
            transaction.external_payment_response = (
                'Succesful AUTHORISATION notification'
            )
            transaction.external_transaction_id = notification_data['pspReference']
            transaction.save()
            tx_log_message = LOG_MESSAGE_TX_SUCESS.format(
                self.id,
                self.notification_name,
                transaction.pk,
                notification_data['pspReference'],
            )
            logger.info(tx_log_message)

        if subscription.status in [
            Subscription.STATUS_CREATED,
            Subscription.STATUS_GRACE_PERIOD,
        ]:
            subscription.status = Subscription.STATUS_ACTIVE
            subscription.valid_until = None
            subscription.grace_period_until = None
            subscription.save()

            sub_log_message = LOG_MESSAGE_SUB_SUCESS.format(
                self.id,
                self.notification_name,
                transaction.pk,
                notification_data['pspReference'],
                subscription.pk,
            )
            logger.info(sub_log_message)

        if (
            self._get_recurring_detail_reference(notification_data) is not None
            or not transaction.payment_method
        ):
            payment_method = get_or_create_payment_method(
                subscription.user, notification_data
            )
            transaction.payment_method = payment_method
            subscription.payment_method = transaction.payment_method
            transaction.save()
            subscription.save()
            logger.info(
                f'Adyen notification handler txid= {self.id} Success {self.notification_name} updated payment_method_id={payment_method.pk}'
            )

    def handle(self, notification_data):
        try:
            auth_notification_type = self._get_auth_notification_type(notification_data)
            if auth_notification_type == 'auth':
                self._confirm_or_update_payment_method(notification_data)
                return True
            transaction_id = notification_data['merchantReference']
            success = notification_data['success']
            transaction = PaymentTransaction.objects.get(pk=transaction_id)
            subscription = transaction.subscription
        except Exception as e:
            logger.warning(
                f'PANIC!. Unable to collect basic data for processing for: {notification_data} error {e} '
            )
            return False

        if success != 'true':
            self._confirm_or_update_on_failed_tx(
                transaction, subscription, notification_data
            )
        else:
            self._confirm_or_update_on_success_tx(
                transaction, subscription, notification_data
            )
        return True


class AdyenNoificationsHandler(object):
    def __init__(self):
        self.id = uuid4()
        self.handlers = {
            'AUTHORISATION': HandleAUTHORISATION,
            'CHARGEBACK': HandleDisputeNotifications,
            'CHARGEBACK_REVERSED': HandleDisputeNotifications,
            'SECOND_CHARGEBACK': HandleDisputeNotifications,
            'NOTIFICATION_OF_FRAUD': HandleFraudNotification,
            'REFUND': HandleRefundNotification,
        }

    def process_notification(self, payload):
        notification_items = payload['notificationItems']
        for notification_request_item in notification_items:
            notification_data = notification_request_item['NotificationRequestItem']
            event = notification_data['eventCode']
            logger.info(
                f"Handler Received Adyen notification: {event} - {notification_data}"
            )
            handler = self.handlers.get(event, None)
            if handler is None:
                logger.info(f'{event} handler not implemented')
            else:
                done = handler().handle(notification_data)
                return done

        return True
