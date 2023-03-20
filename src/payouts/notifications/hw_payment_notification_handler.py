from uuid import uuid4
from amuse.logging import logger
from payouts.models import Event, TransferMethod, Payment
from amuse.vendor.revenue.client import (
    update_withdrawal,
    refund,
)
from payouts.receipt import get_last_payment_return_reason
from slayer.clientwrapper import (
    update_royalty_advance_offer,
    refund_royalty_advance_offer,
)
from payouts.ffwd import FFWDHelpers


class HWPaymentNotificationHandler(object):
    internal_statuses = {
        "SCHEDULED": "PENDING",
        "PENDING_ACCOUNT_ACTIVATION": "PENDING",
        "PENDING_ID_VERIFICATION": "PENDING",
        "PENDING_TAX_VERIFICATION": "PENDING",
        "PENDING_TRANSFER_METHOD_ACTION": "PENDING",
        "PENDING_TRANSACTION_VERIFICATION": "PENDING",
        "IN_PROGRESS": "PENDING",
        "WAITING_FOR_SUPPLEMENTAL_DATA": "PENDING",
        "UNCLAIMED": "EXPIRED",
        "COMPLETED": "COMPLETED",
        "FAILED": "FAILED",
        "RECALLED": "CANCELLED",
        "RETURNED": "RETURNED",
        "EXPIRED": "EXPIRED",
        "CANCELLED": "CANCELLED",
    }

    def __init__(self, payload):
        self.id = uuid4()
        self.payload = payload
        self.token = None
        self.status = None
        self.amuse_paymet_id = None
        self.ignore_list = ["CREATED", "IN_PROGRESS"]

    def _parse_payload(self):
        self.token = self.payload['object']['token']
        self.status = self.payload['object']['status']
        self.amuse_paymet_id = self.payload['object']['clientPaymentId']

    def _new_status_not_allowed(self, current_status, new_status):
        '''
        In some cases Hyperwallet notifications ordering is wrong and this method will
        be used to detect that cases
        :param current_status:
        :param new_status:
        :return:
        '''
        if current_status == "COMPLETED" and new_status not in [
            "RETURNED",
            "RECALLED",
            "COMPLETED",
        ]:
            return True
        # Any transition from RETURNED or RECALLED is not allowed
        if current_status in ["RETURNED", "RECALLED"]:
            return True

    def _save_event(self):
        Event.objects.create(
            object_id=self.token,
            reason="HW notification",
            initiator="SYSTEM",
            payload=self.payload,
        )

    def _update_payment(self, payment):
        payment.status = self.status
        payment.save()

    def _send_event(self, payment):
        """
        Send event to customer.io with payment return reason.
        For now just try to extract RETURNED reason and log.
        TO DO: Create event and send data
        :return:
        """
        payee = payment.payee
        user = payee.user
        try:
            return_reason = get_last_payment_return_reason(payee=payee)
            logger.info(
                f"txid={self.id} Return reason {return_reason} for user {user.email}"
            )
        except Exception as e:
            logger.info(f"txid={self.id} Failed to get RETURNED reason {str(e)}")

    def _update_revenue_system_advance(self, payment):
        internal_status = self.internal_statuses.get(self.status)
        if internal_status in ["CANCELLED", "EXPIRED", "FAILED"]:
            cancellation_response = update_royalty_advance_offer(
                payment.payee.user.pk,
                payment.revenue_system_id,
                "cancel",
                description="New Hyperwallet API integration notification",
            )
            logger.info(
                f"txid={self.id} FFWD payment failed: Payment: {payment.external_id}  Slayer response: {cancellation_response}"
            )
            FFWDHelpers.unlock_splits(payment.payee.user.pk)

        if internal_status == "COMPLETED":
            complete_response = update_royalty_advance_offer(
                payment.payee.user.pk,
                payment.revenue_system_id,
                "activate",
                description="New Hyperwallet API integration notification",
                payment_id=str(payment.pk),
            )
            logger.info(
                f"txid={self.id} FFWD payment succeeded: Payment: Payment: {payment.external_id}  Slayer response: {complete_response}"
            )

        if internal_status == "RETURNED":
            # TODO on revenue system side
            refund_royalty_advance_offer(
                user_id=payment.payee.user.pk,
                royalty_advance_id=payment.revenue_system_id,
                refund_amount_currency="USD",
                refund_amount=float(self.payload['object']['amount']),
                description=f"Hyperwallet return {self.payload['object']['token']}",
                refund_reference=str(payment.pk),
            )
            logger.info(
                f"txid={self.id} FFWD payment returned: Payment: Payment: {payment.external_id}"
            )

            """"
            TODO: this assumes the splits that are locked are so because of the returned advance, it might not be the case,
            They might be locked due to a more recent advance if the returned advance has already recouped,
            and a new ones has been accepted
            """
            FFWDHelpers.unlock_splits(payment.payee.user.pk)

        # Pending event does not affect revenue transaction status
        if internal_status == "PENDING":
            logger.info(
                f"txid={self.id} Not updating PENDING FFWD payment: {payment.external_id}"
            )

    def _update_revenue_system_royalty(self, revenue_system_transaction_id, payment):
        """
        Will be used informing revenue system once Payment has final state
        (COMPLETED, FAILED, EXPIRED, CANCELLED, RETURNED)
        :return:
        """

        internal_status = self.internal_statuses[self.status]
        if internal_status in ["CANCELLED", "EXPIRED", "FAILED"]:
            update_withdrawal(revenue_system_transaction_id, "is_cancelled")
            logger.info(
                f"txid={self.id} Updated revenue system with status {self.status} payload: {self.payload}"
            )
        if internal_status == "COMPLETED":
            update_withdrawal(revenue_system_transaction_id, "is_complete")
            logger.info(
                f"txid={self.id} Updated revenue system with status {self.status} payload: {self.payload}"
            )
        if internal_status == "RETURNED":
            refund(
                payment.payee_id,
                revenue_system_transaction_id,
                self.payload['object']['token'],
                self.payload['object']['amount'],
            )
            logger.info(
                f"Posted new refund to revenue system {self.status} payload: {self.payload}"
            )
        # Pending event does not affect revenue transaction status
        if internal_status == "PENDING":
            logger.info(
                f"txid={self.id} Not updating revenue system with status {self.status} payload: {self.payload}"
            )

    def handle(self):
        logger.info(f"txid={self.id} HW payment handler {self.payload}")
        is_success = False
        try:
            self._parse_payload()
            payment = Payment.objects.get(pk=self.amuse_paymet_id)
            new_status_not_allowed = self._new_status_not_allowed(
                current_status=payment.status, new_status=self.status
            )
            if self.status in self.ignore_list or new_status_not_allowed:
                logger.info(
                    f"txid={self.id} HW payment notification handler skipping {self.status} notification"
                )
                is_success = True
            elif payment.external_id == 'pmt-init' and self.status != 'FAILED':
                logger.info(
                    f"Received premature notification for payment_id={payment.pk}. is_success={is_success}"
                )
            else:
                self._save_event()
                self._update_payment(payment=payment)
                if payment.payment_type == Payment.TYPE_ROYALTY:
                    self._update_revenue_system_royalty(
                        payment.revenue_system_id, payment
                    )
                else:
                    self._update_revenue_system_advance(payment)
                is_success = True
        except Exception as e:
            logger.info(
                f"txid={self.id} HW payment notification handler FAILED error={str(e)} payload {self.payload}"
            )
        finally:
            if is_success and self.status in ['RETURNED', "RECALLED"]:
                self._send_event(payment=payment)
            return {"is_success": is_success}
