def adyen_notification(merchant_account, payment_id, user_id):
    return {
        'NotificationRequestItem': {
            'additionalData': {
                'chargebackReasonCode': '10.4',
                'modificationMerchantReferences': '',
                'chargebackSchemeCode': 'visa',
                'hmacSignature': '1337',
            },
            'amount': {'currency': 'EUR', 'value': 1000},
            'eventCode': 'CHARGEBACK',
            'eventDate': '2018-03-23T13:55:31+01:00',
            'merchantAccountCode': merchant_account,
            'merchantReference': str(user_id),
            'originalReference': str(payment_id),
            'paymentMethod': 'visa',
            'pspReference': '9915555555555555',
            'reason': 'Other Fraud-Card Absent Environment',
            'success': 'true',
        }
    }
