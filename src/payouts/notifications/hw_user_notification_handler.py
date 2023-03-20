from uuid import uuid4
from amuse.logging import logger
from payouts.models import Payee, Event


class HWUserNotificationHandler(object):
    def __init__(self, payload):
        self.payload = payload
        self.id = self.id = uuid4()
        self.ignore_list = ["CREATED"]
        self.token = None
        self.status = None
        self.verification_status = None

    def _parse_payload(self):
        self.token = self.payload['object']['token']
        self.status = self.payload['object']['status']
        self.verification_status = self.payload['object']['verificationStatus']

    def _save_event(self):
        Event.objects.create(
            object_id=self.token,
            reason="HW notification",
            initiator="SYSTEM",
            payload=self.payload,
        )

    def _update_payee(self, payee):
        payee.status = self.status
        payee.verification_status = self.verification_status
        payee.save()

    def _send_event(self):
        """
        Will be used for sending events to segment.io or customer.io
        where we need to inform user on important event or for analytics.
        :return:
        """
        pass

    def handle(self):
        is_success = False
        try:
            self._parse_payload()
            if self.status in self.ignore_list:
                logger.info(
                    f"HW User notification handler skipping {self.status} notification"
                )
                is_success = True
            else:
                payee = Payee.objects.get(external_id=self.token)
                self._update_payee(payee=payee)
                self._save_event()
                is_success = True
        except Exception as e:
            logger.warning(
                f"HW User notification handler FAILED error={e} payload {self.payload}"
            )
        finally:
            if is_success:
                self._send_event()
            return {"is_success": is_success}
