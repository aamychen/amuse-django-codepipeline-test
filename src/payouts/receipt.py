from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory


class UserReceipts(object):
    def __init__(self, payee):
        self.payee = payee
        self.hw_api_client = HyperWalletEmbeddedClientFactory().create(
            payee.user.country
        )
        self.receipts = None

    def fetch_user_receipts(self):
        response = self.hw_api_client.listReceiptsForUser(
            userToken=self.payee.external_id
        )
        self.receipts = [r.asDict() for r in response]

    def get_last_transfer_return(self):
        returns = [tx for tx in self.receipts if "TRANSFER_RETURN" in tx['type']]
        return returns[-1]

    def get_last_transfer_return_reason(self):
        self.fetch_user_receipts()
        last_transfer_return = self.get_last_transfer_return()
        details = last_transfer_return.get("details")
        if details is not None:
            return details['returnOrRecallReason']


def get_last_payment_return_reason(payee):
    user_receipts = UserReceipts(payee=payee)
    return user_receipts.get_last_transfer_return_reason()
