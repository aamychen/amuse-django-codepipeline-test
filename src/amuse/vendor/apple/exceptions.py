class EmptyAppleReceiptError(Exception):
    pass


class DuplicateAppleSubscriptionError(Exception):
    pass


class DuplicateAppleTransactionIDError(Exception):
    pass


class MaxRetriesExceededError(Exception):
    pass


class UnknownAppleError(Exception):
    pass
