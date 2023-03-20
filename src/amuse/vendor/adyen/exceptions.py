import logging

from payments.models import PaymentTransaction


logger = logging.getLogger(__name__)


class PaymentError(Exception):
    message = 'Payment failed'

    def __init__(self, result_code, payment, response):
        self.result_code = result_code
        self.payment = payment
        self.response = response


class CheckoutError(PaymentError):
    status = PaymentTransaction.STATUS_ERROR

    def __init__(self, payment, adyen_exception):
        self.payment = payment
        self.external_transaction_id = getattr(adyen_exception, 'psp', '')
        self.message = 'Error for payment with id %s: %s' % (payment.pk, self)
        self.response = adyen_exception.raw_response
        logger.info(self.message)


class PaymentPendingResponse(PaymentError):
    status = PaymentTransaction.STATUS_PENDING


class PaymentReceivedResponse(PaymentError):
    status = PaymentTransaction.STATUS_PENDING


class PaymentCancelledResponse(PaymentError):
    status = PaymentTransaction.STATUS_CANCELED


class PaymentRefusedResponse(PaymentError):
    status = PaymentTransaction.STATUS_DECLINED


class PaymentErrorResponse(PaymentError):
    status = PaymentTransaction.STATUS_ERROR


class PaymentActionResponse(PaymentError):
    status = PaymentTransaction.STATUS_NOT_SENT


class PaymentUnknownResponse(PaymentError):
    status = PaymentTransaction.STATUS_ERROR

    def __init__(self, result_code, payment, response):
        super().__init__(result_code, payment, response)
        self.message = "PaymentTransaction %s got unsupported result code '%s'" % (
            payment.pk,
            result_code,
        )


class IssuerCountryAPIError(Exception):
    pass
