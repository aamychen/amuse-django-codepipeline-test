from datetime import datetime, timezone


def parse_timestamp_ms(timestamp_ms):
    if timestamp_ms is None:
        return None
    date = datetime.utcfromtimestamp(int(timestamp_ms) / 1000)
    return date.astimezone(timezone.utc)


def process_receipt_simple(payload):
    unified = payload.get('unified_receipt', None)
    last_receipt_info = unified.get('latest_receipt_info', None)
    pending_renewals = unified.get('pending_renewal_info', None)
    sorted_by_purchase = sorted(
        last_receipt_info, key=lambda k: int(k['purchase_date_ms']), reverse=True
    )
    return {'txs': sorted_by_purchase, 'pending_renewals': pending_renewals}


def process_receipt_extended(payload):
    unified = payload.get('unified_receipt', None)
    last_receipt_info = unified.get('latest_receipt_info', None)
    pending_renewals = unified.get('pending_renewal_info', None)
    sorted_by_purchase = sorted(
        last_receipt_info, key=lambda k: int(k['purchase_date_ms']), reverse=True
    )
    original_transaction = sorted_by_purchase[-1]
    last_transaction = sorted_by_purchase[0]
    next_to_last = None
    is_upgraded = None
    if len(sorted_by_purchase) > 1:
        next_to_last = sorted_by_purchase[1]
        is_upgraded = next_to_last.get('is_upgraded')

    all_tx_ids = [k['transaction_id'] for k in sorted_by_purchase]
    last_expires_date = parse_timestamp_ms(last_transaction['expires_date_ms'])

    return {
        'txs': sorted_by_purchase,
        'pending_renewals': pending_renewals,
        'original_transaction': original_transaction,
        'last_transaction': last_transaction,
        'next_to_last_transaction': next_to_last,
        'is_upgraded': is_upgraded,
        'all_tx_ids': all_tx_ids,
        'last_expires_date': last_expires_date,
        'latest_receipt': unified['latest_receipt'],
    }


def process_receipt_cancel(payload):
    unified = payload.get('unified_receipt', None)
    last_receipt_info = unified.get('latest_receipt_info', None)
    sorted_by_purchase = sorted(
        last_receipt_info, key=lambda k: int(k['purchase_date_ms']), reverse=True
    )
    original_transaction = sorted_by_purchase[-1]
    last_transaction = sorted_by_purchase[0]
    is_last_transaction_cancel = (
        last_transaction.get('cancellation_date_ms') is not None
    )
    is_upgrade = (
        is_last_transaction_cancel and last_transaction.get('is_upgraded') is not None
    )
    cancel_txs = [k for k in sorted_by_purchase if 'cancellation_date_ms' in k]
    cancel_purchase_date = [k['purchase_date_ms'] for k in cancel_txs]
    all_tx_ids = [k['transaction_id'] for k in sorted_by_purchase]

    return {
        'simple_case': len(last_receipt_info) == 1,
        'all_tx_ids': all_tx_ids,
        'txs': sorted_by_purchase,
        'original_transaction': original_transaction,
        'cancel_txs': cancel_txs,
        'is_last_transaction_cancel': is_last_transaction_cancel,
        'is_upgrade': is_upgrade,
        'cancel_purchase_date': cancel_purchase_date,
    }
