import requests
from django.conf import settings
from amuse.logging import logger

"""
Server side verification of user response to reCAPTCHA v3 challenge.
Function verify() does not offer any interpretation of the results since that logic may differ
it only tries to verify client side token and provides results of that operation
as they returned by google reCAPTCHA v3 service described here:
https://developers.google.com/recaptcha/docs/verify
"""

GOOGLE_CAPTCHA_ERROR_CODES = [
    "timeout-or-duplicate",
    "bad-request",
    "invalid-input-response",
    "missing-input-response",
    "invalid-input-secret",
    "missing-input-secret",
]

CAPTCHA_SYSTEM_ERROR_CODES = ["request-exception", "invalid-response-code"]


def verify(client_side_token: str, remote_ip: str = "") -> dict:
    """
    Each reCAPTCHA user
    response token is valid for TWO MINUTES, and can only be verified ONCE to
    prevent replay attacks
    :param client_side_token: str value provide by clients
    :param remote_ip: optional parameter user's IP
    :return: dict result of client token verification
    """
    if not settings.GOOGLE_CAPTCHA_ENABLED:
        return {'success': True, 'score': 1.0}

    payload = {
        "secret": settings.GOOGLE_CAPTCHA_SECRET_KEY,
        "response": client_side_token,
        "remoteip": remote_ip,
    }
    try:
        response = requests.post(
            url=settings.GOOGLE_CAPTCHA_ENDPOINT, data=payload, timeout=5
        )
        response_status = response.status_code
        if response_status != 200:
            error_code = "invalid-response-code"
            return {"success": False, "error-codes": [error_code]}
        else:
            return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to verify reCAPTCHA error={str(e)}")
        error_code = "request-exception"
        return {"success": False, "error-codes": [error_code]}


def is_human(
    client_side_token: str, remote_ip: str = "", captcha_type: str = 'v2'
) -> bool:
    """
    reCAPTCHA v2
    Interpret reCAPTCHA verify result:
    - If check is successful return True

    reCAPTCHA v3
    Interpret reCAPTCHA verify result:
    -   If check is successful and score is **gt** GOOGLE_CAPTCHA_SCORE_THRESHOLD return True
    -   If check is successful and score is **lt** GOOGLE_CAPTCHA_SCORE_THRESHOLD return False
    -   If check is not successful and error code indicate that client side token is
    manipulated, or not valid return False
    -   If check is not successful and error code indicate network or server issue
    return True to avoid issue when google service is not available.

    :param client_side_token: str
    :param remote_ip: str
    :param captcha_type: str default v2
    :return: bool
    """
    verify_result = verify(client_side_token=client_side_token, remote_ip=remote_ip)
    verify_status = verify_result['success']
    if verify_status and captcha_type == 'v2':
        return True
    if verify_status and captcha_type == 'v3':
        verify_score = verify_result.get('score', 0.0)
        if verify_score < float(settings.GOOGLE_CAPTCHA_SCORE_THRESHOLD):
            return False
        return True
    if not verify_status:
        error_codes = verify_result['error-codes']
        for error in error_codes:
            if error in CAPTCHA_SYSTEM_ERROR_CODES:
                return True
        return False
