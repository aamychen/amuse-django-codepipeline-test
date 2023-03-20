from payments.models import PaymentTransaction


def create_apple_payment(**kwargs):
    is_loaded = PaymentTransaction.objects.filter(
        external_transaction_id=kwargs['external_transaction_id']
    ).exists()
    if is_loaded:
        return False

    return PaymentTransaction.objects.create(**kwargs)
