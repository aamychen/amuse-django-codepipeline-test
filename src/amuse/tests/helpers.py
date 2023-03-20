import base64
from datetime import timedelta

import responses
from django.utils import timezone


ZENDESK_MOCK_API_URL_TOKEN = {
    "ZENDESK_API_URL": "https://zendesk-mock-host",
    "ZENDESK_API_TOKEN": "fake-token",
}

HYPERWALLET_API_SANDBOX_URL = "https://api.sandbox.hyperwallet.com/rest/v3/"

FUGA_MOCK_SETTINGS = {
    "FUGA_API_URL": "https://fuga-mock-host/",
    "FUGA_API_USER": "test",
    "FUGA_API_PASSWORD": "test",
}


def build_auth_header(user, password):
    auth = base64.b64encode(f'{user}:{password}'.encode()).decode()
    return {'HTTP_AUTHORIZATION': f'Basic {auth}'}


def add_zendesk_mock_post_response():
    return responses.add(
        responses.POST,
        'https://zendesk-mock-host/api/v2/users/create_or_update.json',
        status=200,
    )


def zendesk_mock_show_job_status_response(zendesk_host, job_id):
    return {
        "job_status": {
            "id": job_id,
            "message": "Completed at Fri Apr 13 02:51:53 +0000 2012",
            "progress": 2,
            "results": [
                {"action": "update", "id": 380, "status": "Updated", "success": True}
            ],
            "status": "completed",
            "total": 2,
            "url": f"https://{zendesk_host}/api/v2/job_statuses/{job_id}.json",
        }
    }


def zendesk_mock_create_many_tickets_request():
    return [
        {
            "comment": {"body": "The smoke is very colorful."},
            "priority": "urgent",
            "subject": "My printer is on fire!",
        },
        {
            "comment": {"body": "This is a comment"},
            "priority": "normal",
            "subject": "Help",
        },
    ]


def zendesk_mock_create_many_tickets_response(zendesk_host, job_id):
    return {
        "job_status": {
            "id": f"{job_id}",
            "message": "Completed at 2018-03-08 10:07:04 +0000",
            "progress": 2,
            "results": [
                {"action": "update", "id": 244, "status": "Updated", "success": True},
                {"action": "update", "id": 245, "status": "Updated", "success": True},
            ],
            "status": "completed",
            "total": 2,
            "url": f"https://{zendesk_host}/api/v2/job_statuses/{job_id}.json",
        }
    }


def hyperwallet_mock_payload_create_user(user, program_token):
    return {
        "clientUserId": user.id,
        "email": user.email,
        "profileType": "INDIVIDUAL",
        "programToken": program_token,
        "phoneNumber": user.phone,
        "firstName": user.first_name,
        "lastname": user.last_name,
        "country": user.country,
    }


def hyperwallet_mock_response_create_user(user, user_token, program_token):
    return {
        "token": user_token,
        "status": "PRE_ACTIVATED",
        "createdOn": "2017-10-30T22:15:45",
        "clientUserId": user.id,
        "profileType": "INDIVIDUAL",
        "email": user.email,
        "phoneNumber": user.phone,
        "language": "en",
        "programToken": program_token,
        "links": [
            {
                "params": {"rel": "self"},
                "href": "https://api.sandbox.hyperwallet.com/rest/v3/users/usr-f9154016-94e8-4686-a840-075688ac07b5",
            }
        ],
    }


def hyperwallet_mock_payload_create_payment(user_token, transaction_id, program_token):
    return {
        "amount": "20.00",
        "clientPaymentId": transaction_id,
        "currency": "USD",
        "destinationToken": user_token,
        "programToken": program_token,
        "purpose": "OTHER",
    }


def hyperwallet_mock_response_create_payment(user_token, transaction_id, program_token):
    return {
        "token": "pmt-87939c73-ff0a-4011-970e-3de855347ea7",
        "status": "COMPLETED",
        "createdOn": "2017-10-31T22:48:52",
        "amount": "18.94",
        "currency": "USD",
        "clientPaymentId": transaction_id,
        "purpose": "OTHER",
        "expiresOn": "2018-04-29",
        "destinationToken": user_token,
        "programToken": program_token,
        "links": [
            {
                "params": {"rel": "self"},
                "href": "https://api.sandbox.hyperwallet.com/rest/v3/payments/pmt-87939c73-ff0a-4011-970e-3de855347ea7",
            }
        ],
    }


def hyperwallet_mock_response_error():
    return {
        "errors": [
            {
                "message": "The value you provided for this field is already registered with another user usr-ae836d14-f4f4-4d6d-9653-1ee03250df7b",
                "fieldName": "clientUserId",
                "code": "DUPLICATE_CLIENT_USER_ID",
                "relatedResources": ["usr-ae836d14-f4f4-4d6d-9653-1ee03250df7b"],
            }
        ]
    }


def release_V4_payload(release_artist, song_artist, genre, release_date=None):
    if release_date is None:
        release_date = timezone.now().date() + timedelta(days=30)
    return {
        'name': 'Postman Release (v4)',
        'label': None,
        'cover_art_filename': 'cover.jpg',
        'release_date': release_date.strftime('%Y-%m-%d'),
        'excluded_stores': [],
        'excluded_countries': [],
        'upc': '',
        'artist_id': release_artist.id,
        'songs': [
            {
                'name': 'Test Song 1',
                'sequence': 1,
                'version': 'Version Title',
                'explicit': 'clean',
                'recording_year': 2018,
                'filename': 'users_filename.wav',
                'origin': 'remix',
                'isrc': '',
                'audio_s3_key': 'wave.wav',
                'youtube_content_id': 'none',
                'cover_licensor': '',
                'genre': {'id': genre.id, 'name': genre.name},
                'artists_roles': [
                    {'roles': ['primary_artist'], 'artist_id': song_artist.id}
                ],
                'royalty_splits': [{'user_id': song_artist.owner.id, 'rate': 1.00}],
            }
        ],
    }


mock_unknown_error_response = {'errors': [{'message': 'unknown', 'code': 'unknown'}]}
mock_limit_subceeded_response = {
    'errors': [
        {
            'message': 'Requested transfer amount $8.55, is below the transaction limit of $20.00.',
            'code': 'LIMIT_SUBCEEDED',
        }
    ]
}
mock_firstname_constraint_response = {
    'errors': [
        {
            'message': 'is invalid length or format.',
            'fieldName': 'firstName',
            'code': 'CONSTRAINT_VIOLATIONS',
        }
    ]
}
mock_lastname_constraint_response = {
    'errors': [
        {
            'message': 'is invalid length or format.',
            'fieldName': 'lastName',
            'code': 'CONSTRAINT_VIOLATIONS',
        }
    ]
}
mock_incorrect_funding_program_response = {
    'errors': [
        {
            'message': 'You are not configured to use the specified funding program',
            'code': 'INCORRECT_FUNDING_PROGRAM',
        }
    ]
}
mock_invalid_wallet_status_response = {
    'errors': [
        {
            'message': 'The account status does not allow the requested action.',
            'code': 'INVALID_WALLET_STATUS',
        }
    ]
}
mock_store_invalid_currency_response = {
    'errors': [{'message': 'Invalid currency.', 'code': 'STORE_INVALID_CURRENCY'}]
}
mock_duplicate_extra_id_type_response = {
    'errors': [
        {
            'message': 'The client user identifier you provided is already registered with another user',
            'code': 'DUPLICATE_EXTRA_ID_TYPE',
        }
    ]
}


def mock_royalty_advance_offer(user_id, offer=True):
    response = {"user_id": user_id}

    if offer:
        response.update(
            {
                "id": "12345678-1234-1234-1234-12345678901",
                "expires_at": "2020-06-30T10:00:00.000Z",
                "created_at": "2020-06-07T10:00:20.000Z",
                "total_amount": 1234.12,
                "total_fee_amount": 123.412,
                "total_user_amount": 1110.708,
                "effective_fee_rate": 0.1,
                "currency": "USD",
                "split_ids_for_locking": ["303309", "1420625"],
            }
        )

    return response


def mock_validate_offer(
    user_id,
    royalty_advance_offer_id,
    is_valid=True,
    create_pending_transactions=True,
    split_ids=None,
    withdrawal_total=89.578_018_249_999_9,
    royalty_advance_id="585b4596-d3fb-45f0-a373-177ff0e4ae70",
):
    if not is_valid:
        return {"user_id": user_id, "validation_failure_reason": "OFFER_EXPIRED"}

    response = {
        "user_id": user_id,
        "royalty_advance_offer_id": royalty_advance_offer_id,
        "is_valid": True,
        "royalty_advance_offer": {
            "id": royalty_advance_offer_id,
            "user_id": "117004",
            "expires_at": "2020-07-31T00:00:00Z",
            "created_at": "2020-07-08T00:19:13Z",
            "total_amount": 237.230_638_801,
            "total_fee_amount": 42.650_843_657,
            "total_user_amount": 194.579_795_144,
            "effective_fee_rate": 0.179_786_404_793_933_46,
            "currency": "USD",
        },
        "withdrawal_total": withdrawal_total,
        "withdrawal_advance": 61.0,
        "withdrawal_balance": 28.578_018_249_999_9,
        "royalty_advance_id": royalty_advance_id,
        "advance_transaction_id": "fc20bff0-e761-4f77-ad8a-66c9ef34ec66",
        "fee_transaction_id": "45dac424-f981-431f-9feb-8684d4a888f4",
        "balance_transaction_id": "61774cd6-b5c0-4301-a9aa-192b1b6aac22",
    }

    if create_pending_transactions:
        response["royalty_advance_id"] = "585b4596-d3fb-45f0-a373-177ff0e4ae70"
        response["advance_transaction_id"] = "fc20bff0-e761-4f77-ad8a-66c9ef34ec66"
        response["fee_transaction_id"] = "45dac424-f981-431f-9feb-8684d4a888f4"
        response["balance_transaction_id"] = "61774cd6-b5c0-4301-a9aa-192b1b6aac22"

    if split_ids:
        response["royalty_advance_offer"]["split_ids_for_locking"] = split_ids

    return response


def mock_update_offer(user_id, advance_id, action, is_valid):
    response = {"user_id": user_id, "royalty_advance_id": advance_id}
    if is_valid:
        if action == "activate":
            response["is_active"] = True
        elif action == "cancel":
            response["is_cancelled"] = True

    return response
