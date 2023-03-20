import base64
import json

import requests
from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2 import service_account


class ReleaseAnalysisApiError(Exception):
    pass


def get_results(release_id):
    json_response = make_request(release_id)
    response = json.loads(json_response.text)
    format_response(response)
    return response


def make_request(release_id):
    url = f'https://release-analysis.amuse.io/warnings/release/{release_id}'

    resp = requests.request(
        'GET',
        url,
        headers={'Authorization': 'Bearer {}'.format(generate_token())},
        timeout=10,
    )

    if resp.status_code == 403:
        raise ReleaseAnalysisApiError(
            'Service account does not have permission to '
            'access the IAP-protected release analysis service.'
        )
    elif resp.status_code != 200:
        raise ReleaseAnalysisApiError(
            'Bad response from application: {!r} / {!r} / {!r}'.format(
                resp.status_code, resp.headers, resp.text
            )
        )
    else:
        return resp


def generate_token():
    if (
        settings.GCP_SERVICE_ACCOUNT_JSON is None
        or settings.RELEASE_ANALYSIS_CLIENT_ID is None
    ):
        raise ValueError(
            'Missing credentials to connect to the release analysis service'
        )

    service_account_json = json.loads(
        base64.b85decode(settings.GCP_SERVICE_ACCOUNT_JSON).decode('UTF-8')
    )

    client_id = settings.RELEASE_ANALYSIS_CLIENT_ID

    credentials = service_account.IDTokenCredentials.from_service_account_info(
        service_account_json, target_audience=client_id
    )
    credentials.refresh(Request())
    return credentials.token


def format_response(response):
    # format warnings
    for acr_warning in response['acr_cloud_warnings']:
        format_acr_warning(acr_warning)

    # filter out ones that will not be shown
    response['acr_cloud_warnings'] = [
        warning
        for warning in response['acr_cloud_warnings']
        if warning['show_warning_on_track_level']
    ]

    # Create dict of warnings keyed by track id
    warnings_structured_by_track = {}
    tracks_with_warnings = []
    tracks_with_critical_warnings = []

    if response.get('has_warning'):
        for warnings in response.values():
            if not isinstance(warnings, list):
                continue

            for warning in warnings:
                if warning.get('track_id'):
                    warnings_structured_by_track[
                        warning['track_id']
                    ] = warnings_structured_by_track.get(warning['track_id'], []) + [
                        warning
                    ]
                    tracks_with_warnings.append(int(warning['track_id']))

                    if warning['show_warning']:
                        tracks_with_critical_warnings.append(int(warning['track_id']))

    response['tracks'] = warnings_structured_by_track
    response['tracks_with_warnings'] = tracks_with_warnings
    response['tracks_with_critical_warnings'] = tracks_with_critical_warnings


def format_acr_warning(warning):
    warning['show_warning_on_track_level'] = False
    warning['contains_major_label_match'] = False

    if 'acr_cloud_warning_matches' in warning:
        for acr_cloud_matches in warning['acr_cloud_warning_matches']:
            # Calculate average score over all segments
            scores = [
                acr_result['score']
                for acr_result in acr_cloud_matches['acr_cloud_results']
            ]
            acr_cloud_matches['score'] = sum(scores) / len(
                acr_cloud_matches['acr_cloud_results']
            )

            # Determine if warning to be shown on track level
            if (
                len(acr_cloud_matches['acr_cloud_results']) == 1
                and acr_cloud_matches['score'] >= 80
            ) or (
                len(acr_cloud_matches['acr_cloud_results']) >= 2
                and acr_cloud_matches['score'] >= 70
            ):
                warning['show_warning_on_track_level'] = True

            # Calculate distributor where possible
            formatted_distributor = ""

            acr_cloud_matches['is_major_label_distributor'] = False
            first_acr_result = acr_cloud_matches['acr_cloud_results'][0]
            if first_acr_result.get('apple_store_matches'):
                distributor = first_acr_result['apple_store_matches'][0]['collection'][
                    'content_provider_name'
                ]
                acr_cloud_matches[
                    'is_major_label_distributor'
                ] = is_major_label_distributor(distributor)
                formatted_distributor = format_apple_distributor(distributor)

                if (
                    acr_cloud_matches['is_major_label_distributor']
                    and acr_cloud_matches['score'] >= 70
                ):
                    warning['contains_major_label_match'] = True

                if first_acr_result['result']:
                    acr_cloud_matches['duration_ms'] = first_acr_result['result'].get(
                        'duration_ms'
                    )

            acr_cloud_matches['distributor'] = formatted_distributor

        # Sort based on major label, score + number of matching segments
        warning['acr_cloud_warning_matches'] = sorted(
            warning['acr_cloud_warning_matches'],
            key=lambda d: (
                d['is_major_label_distributor'],
                d['score'],
                len(d['acr_cloud_results']),
            ),
            reverse=True,
        )


def format_apple_distributor(distributor):
    distributor_mapping = {
        "PKInteractiveInc": "Distrokid",
        "PK Interactive, Inc.": "Distrokid",
        "AmuseioAB105905351991": "Amuse",
        "Amuseio AB|10590535199|1": "Amuse",
        "SonyBMG": "Sony",
        "Sony Music": "Sony",
        "Sony Music ": "Sony",
        "BelieveSAS": "Believe",
        "Believe SAS": "Believe",
        "Believe Digital GmbH (formerly Deeep.net Gmbh)": "Believe",
        "AWALUK": "AWAL",
        "AWAL Digital Limited": "AWAL",
        "LANDRAUDIOINC": "Landr",
        "LANDR AUDIO INC.": "Landr",
        "DittoMusic": "Ditto",
        "Ditto Music": "Ditto",
        "StemDisintermediaInc10062613873": "Stem",
        "Stem Distributions LLC.": "Stem",
        "TuneCore": "TuneCore",
        "tunecorejapan": "TuneCore",
        "TuneCore Japan": "TuneCore",
        "TuneCore, Inc": "TuneCore",
        "Phonofile": "TuneCore",
        "Phonofile AS": "TuneCore",
        "IndependentIP": "Fuga",
        "IIP-DDS B.V. (f/k/a Independent IP)": "Fuga",
        "FUGA": "Fuga",
        "EMPIREDistributionInc": "Empire",
        "EMPIRE Distribution Inc.": "Empire",
        "TranslationEnterprisesInc": "United Masters",
        "Translation Enterprises Inc.": "United Masters",
        "Translation Enterprises Inc. ": "United Masters",
        "BMGRightsManagementUKLtd": "BMG",
        "Routenote": "Routenote",
        "Routenote / Insomnia Ltd.": "Routenote",
        "UMI": "Universal",
        "umgglobal": "Universal",
        "bastille": "Universal",
        "AllAroundTheWorldProductionsLtd": "Universal",
        "UMG Global": "Universal",
        "Warner": "Warner",
        "The Warner Music Group": "Warner",
        "CDBaby": "CDBaby",
        "CD Baby / Hit Media": "CDBaby",
        "CD Baby (f/k/a re:discover, Inc.)": "CDBaby",
        "Audio and Video Labs, Inc. DBA CD Baby": "CDBaby",
        "Audio and Video Labs, Inc. DBA Soundrop": "CDBaby",
        "Record Union / DFP Group AB": "Record Union",
        "Orchard": "Orchard",
        "The Orchard Enterprises Inc.": "Orchard",
        "IODA": "Orchard",
        "RepostNetworkInc": "Repost / Soundcloud",
        "Repost Network Inc": "Repost / Soundcloud",
        "GoodToGo GmbH (formerly Groove Attack)": "Groove Attack",
    }

    if distributor in distributor_mapping:
        return distributor_mapping[distributor]
    else:
        return distributor


def is_major_label_distributor(distributor):
    major_distributors = [
        "SonyBMG",
        "Sony Music",
        "Sony Music ",
        "UMI",
        "umgglobal",
        "bastille",
        "AllAroundTheWorldProductionsLtd",
        "UMG Global",
        "Warner",
        "The Warner Music Group",
    ]

    return distributor in major_distributors
