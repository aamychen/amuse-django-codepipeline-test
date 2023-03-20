from datetime import datetime, timedelta


def mock_payment_methods(name='Credit Card'):
    return {
        "groups": [{"name": "Credit Card", "types": ["mc", "visa", "amex"]}],
        "paymentMethods": [
            {
                "brands": ["mc", "visa", "amex"],
                "details": [
                    {"key": "encryptedCardNumber", "type": "cardToken"},
                    {"key": "encryptedSecurityCode", "type": "cardToken"},
                    {"key": "encryptedExpiryMonth", "type": "cardToken"},
                    {"key": "encryptedExpiryYear", "type": "cardToken"},
                    {"key": "holderName", "optional": True, "type": "text"},
                ],
                "name": name,
                "type": "scheme",
            },
            {"name": "Paysafecard", "supportsRecurring": True, "type": "paysafecard"},
        ],
    }


def mock_payment_details():
    return {
        "paymentMethod": {
            "type": "scheme",
            "encryptedExpiryMonth": "",
            "encryptedExpiryYear": "",
            "encryptedSecurityCode": "",
            "encryptedCardNumber": "",
        },
        "browserInfo": {
            "acceptHeader": "*/*",
            "colorDepth": 24,
            "language": "en-US",
            "javaEnabled": True,
            "screenHeight": 900,
            "screenWidth": 1440,
            "userAgent": "agentinfo",
            "timeZoneOffset": -60,
        },
        "billingAddress": {
            "street": "Infinite Loop",
            "houseNumberOrName": "1",
            "postalCode": "95014",
            "city": "Cupertino",
            "stateOrProvince": "CA",
            "country": "US",
        },
    }


def mock_payment_response(
    user,
    result_code="Authorised",
    additional_data=None,
    expiry_date=None,
    is_renewal=False,
    refusal_reason=None,
):
    if expiry_date is None:
        expiry_date = (datetime.now() + timedelta(days=730)).strftime("%m/%Y")

    response = {
        "additionalData": {
            "cardSummary": "9000",
            "expiryDate": expiry_date,
            "issuerCountry": "US",
            "paymentMethod": "visa",
            "recurringProcessingModel": "Subscription",
            "recurring.shopperReference": str(user.pk),
        },
        "pspReference": "852573206663406C",
        "resultCode": result_code,
        "merchantReference": "6",
    }
    # Only authorised payments should store customer card details at Adyen servers and
    # returning the recurring reference for further renewal
    if result_code == "Authorised":
        response["additionalData"][
            "recurring.recurringDetailReference"
        ] = "8415732066637761"
    if additional_data:
        response["additionalData"].update(additional_data)
    if is_renewal:
        response["additionalData"].pop("recurring.recurringDetailReference", None)
    if refusal_reason:
        response['refusalReason'] = refusal_reason
    return response


def mock_payment_redirect():
    """Adyen checkout response payload when the card requires 3DS authentication.

    First the user is redirected to the response['action']['url'], once the user has
    completed the 3DS authentication, he will be redirected to
    response['action']['data']['TermUrl'].
    """
    response = {
        "resultCode": "RedirectShopper",
        "action": {
            "data": {
                "MD": "123",
                "PaReq": "456",
                "TermUrl": "http://app-dev.amuse.io/adyen/3ds/1/",
            },
            "method": "POST",
            "paymentData": "789",
            "paymentMethodType": "scheme",
            "type": "redirect",
            "url": "https://checkoutshopper-test.adyen.com/checkoutshopper/threeDS2.shtml",
        },
        "details": [{"key": "MD", "type": "text"}, {"key": "PaRes", "type": "text"}],
        "paymentData": "000",
        "redirect": {
            "data": {
                "PaReq": "abc",
                "TermUrl": "http://app-dev.amuse.io/adyen/3ds/1/",
                "MD": "def",
            },
            "method": "POST",
            "url": "https://checkoutshopper-test.adyen.com/checkoutshopper/threeDS2.shtml",
        },
    }

    return response


def mock_payment_paypal(result_code="Pending", include_payment_method=True):
    """Adyen checkout response payload when PayPal payment process is initiated
    The user is returned back the 'action' which is rendered by the clients"""

    if result_code == "Pending":
        response = {
            "resultCode": "Pending",
            "action": {
                "type": "sdk",
                "paymentMethodType": "paypal",
                "paymentData": "Ab02b4c0!BQABAgARb1TvUJa4nwS0Z1nOmxoYfD9+z",
                "sdkData": {"token": "EC-42N19135GM6949000"},
            },
        }
    else:
        response = {
            "resultCode": "Authorised",
            "pspReference": "852597655141185C",
            "shopperLocale": "en_GB",
            "merchantReference": "13",
        }
        if include_payment_method:
            response['paymentMethod'] = 'paypal'

    return response


def mock_payment_identify_shopper():
    return {
        'resultCode': 'IdentifyShopper',
        'action': {
            'paymentData': '...',
            'paymentMethodType': 'scheme',
            'token': '...',
            'type': 'threeDS2Fingerprint',
        },
        'authentication': {'threeds2.fingerprintToken': '...'},
        'details': [{'key': 'threeds2.fingerprint', 'type': 'text'}],
        'paymentData': '...',
    }


def mock_payment_challenge_shopper():
    return {
        'resultCode': 'ChallengeShopper',
        'action': {
            'paymentData': '...',
            'paymentMethodType': 'scheme',
            'token': '...',
            'type': 'threeDS2Challenge',
        },
        'authentication': {'threeds2.challengeToken': '...'},
        'details': [{'key': 'threeds2.challengeResult', 'type': 'text'}],
        'paymentData': '...',
    }


def mock_country_check_response(country_code=None):
    response = {
        'cardBin': {'summary': '1234'},
        'resultCode': 'Authorised',
        'surchargeType': 'ZERO',
    }
    if country_code:
        response['cardBin']['issuingCountry'] = country_code
    return response


def mock_country_check_expired_payment_details():
    return {
        "status": 422,
        "errorCode": "172",
        "message": "Encrypted data used outside of valid time period",
        "errorType": "validation",
    }


def mock_country_check_unsupported_payment_details():
    return {
        'status': 500,
        'errorCode': '905',
        'message': 'Payment details are not supported',
        'errorType': 'configuration',
    }
