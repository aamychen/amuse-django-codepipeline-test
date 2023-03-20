import json
import pathlib

import pytest
import responses
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings

from amuse.vendor.fuga.fuga_api import FugaAPIClient

absolute_src_path = pathlib.Path(__file__).parent.parent.resolve()


def load_fixture(filename):
    return open(f"{absolute_src_path}/fixtures/{filename}")


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_fuga_login_successful():
    cookie_string = "magic-fake-cookie-string"

    responses.add(
        responses.POST,
        settings.FUGA_API_URL + "login",
        headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
        status=200,
    )
    client = FugaAPIClient()
    client._login()
    assert client.cookie == {"connect.sid": cookie_string}
    assert client.cookie == cache.get(settings.FUGA_API_CACHE_COOKIE_KEY)


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_fuga_login_failed():
    responses.add(responses.POST, settings.FUGA_API_URL + "login", status=400)

    with pytest.raises(ConnectionError):
        FugaAPIClient()._login()


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_get_fuga_product_id():
    upc = "0714583582432"
    cookie_string = "magic-fake-cookie-string"

    responses.add(
        responses.POST,
        settings.FUGA_API_URL + "login",
        headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
        status=200,
    )
    responses.add(
        responses.GET,
        settings.FUGA_API_URL + "v2/products/?search=%s" % upc,
        status=200,
        json=json.load(load_fixture("FugaSearchByUPC.json")),
    )
    assert FugaAPIClient().get_fuga_product_id(upc) == 1491371962


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_get_fuga_product_id_throws_error():
    upc = 111
    cookie_string = "magic-fake-cookie-string"

    responses.add(
        responses.POST,
        settings.FUGA_API_URL + "login",
        headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
        status=200,
    )
    responses.add(
        responses.GET,
        settings.FUGA_API_URL + "v2/products/?search=%s" % upc,
        status=400,
    )

    with pytest.raises(ConnectionError):
        FugaAPIClient().get_fuga_product_id(upc)


EXPECTED_HISTORY = {
    89882: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    99268: {'action': None, 'lead_time': 'NEVER_DELIVER', 'state': 'BLOCKED'},
    103725: {'action': 'DELIVER', 'lead_time': 'IMMEDIATELY', 'state': 'PROCESSING'},
    103731: {'action': 'DELIVER', 'lead_time': 'IMMEDIATELY', 'state': 'PROCESSING'},
    247916: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    464139: {'action': 'DELIVER', 'lead_time': 'IMMEDIATELY', 'state': 'PROCESSING'},
    746109: {'action': None, 'lead_time': 'NEVER_DELIVER', 'state': 'BLOCKED'},
    1048705: {'action': None, 'lead_time': 'NEVER_DELIVER', 'state': 'BLOCKED'},
    1330598: {'action': None, 'lead_time': 'NEVER_DELIVER', 'state': 'BLOCKED'},
    2100357: {'action': 'DELIVER', 'lead_time': 'IMMEDIATELY', 'state': 'PROCESSING'},
    3440259: {'action': 'DELIVER', 'lead_time': 'IMMEDIATELY', 'state': 'PROCESSING'},
    4266325: {'action': 'DELIVER', 'lead_time': 'IMMEDIATELY', 'state': 'PROCESSING'},
    7851192: {'action': None, 'lead_time': 'NEVER_DELIVER', 'state': 'BLOCKED'},
    9940949: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    13285026: {'action': 'DELIVER', 'lead_time': 'IMMEDIATELY', 'state': 'PROCESSING'},
    20799134: {'action': 'DELIVER', 'lead_time': 'IMMEDIATELY', 'state': 'PROCESSING'},
    49262307: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    62873543: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    78395129: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    121452605: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    316911752: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    847103579: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1130831671: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1158892521: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1186352005: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1207204780: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1209287754: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1210987244: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1226212715: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1232212955: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1234931270: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1382854531: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1415672002: {
        'action': 'DELIVER',
        'lead_time': 'IMMEDIATELY',
        'state': 'PROCESSING',
    },
    1461025062: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1499657856: {
        'action': 'DELIVER',
        'lead_time': 'IMMEDIATELY',
        'state': 'PROCESSING',
    },
    1517454273: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1553828531: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1686928319: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
    1988507361: {'action': None, 'lead_time': 'IMMEDIATELY', 'state': 'NOT_ADDED'},
}


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_fuga_get_delivery_history_with_upc_existing():
    upc = 111
    fuga_id = 222
    cookie_string = "magic-fake-cookie-string"

    responses.add(
        responses.POST,
        settings.FUGA_API_URL + "login",
        headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
        status=200,
    )
    responses.add(
        responses.GET,
        settings.FUGA_API_URL + "v2/products/?search=%s" % upc,
        json={"product": [{"id": fuga_id}]},
        status=200,
    )
    responses.add(
        responses.GET,
        settings.FUGA_API_URL + "v1/products/%s/delivery_instructions" % fuga_id,
        json=json.load(load_fixture("FugaDeliveryInstructions.json")),
        status=200,
    )
    delivery_history = FugaAPIClient().get_delivery_history(upc)
    assert delivery_history == EXPECTED_HISTORY


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_fuga_get_delivery_history_with_upc_not_existing():
    upc = 111
    cookie_string = "magic-fake-cookie-string"

    responses.add(
        responses.POST,
        settings.FUGA_API_URL + "login",
        headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
        status=200,
    )
    responses.add(
        responses.GET,
        settings.FUGA_API_URL + "v2/products/?search=%s" % upc,
        json={"product": []},
        status=200,
    )

    assert FugaAPIClient().get_delivery_history(upc) == {}


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_fuga_get_delivery_history_throws_error():
    upc = 111
    fuga_id = 222
    cookie_string = "magic-fake-cookie-string"

    responses.add(
        responses.POST,
        settings.FUGA_API_URL + "login",
        headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
        status=200,
    )
    responses.add(
        responses.GET,
        settings.FUGA_API_URL + "v2/products/?search=%s" % upc,
        json={"product": [{"id": fuga_id}]},
        status=200,
    )
    responses.add(
        responses.GET,
        settings.FUGA_API_URL + "v1/products/%s/delivery_instructions" % fuga_id,
        status=400,
    )

    with pytest.raises(ConnectionError):
        FugaAPIClient().get_delivery_history(upc)


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_fuga_get_delivery_history_for_dsp():
    fuga_product_id = 2165610288
    fuga_dsp_id = 20799134
    cookie_string = "magic-fake-cookie-string"

    responses.add(
        responses.POST,
        settings.FUGA_API_URL + "login",
        headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
        status=200,
    )
    responses.add(
        responses.GET,
        settings.FUGA_API_URL
        + "v2/products/%s/delivery_instructions/%s/history"
        % (fuga_product_id, fuga_dsp_id),
        json=json.load(load_fixture("FugaDeliveryHistory.json")),
        status=200,
    )
    delivery_history_records = FugaAPIClient().get_delivery_history_for_dsp(
        fuga_product_id, fuga_dsp_id
    )
    assert len(delivery_history_records) == 4
    assert all(
        [record["dsp"]["id"] == fuga_dsp_id for record in delivery_history_records]
    )
    assert all(
        [record["dsp"]["name"] == "Anghami" for record in delivery_history_records]
    )
    assert all(
        [
            record["product"]["id"] == fuga_product_id
            for record in delivery_history_records
        ]
    )


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_fuga_get_artist_identifier():
    fuga_artist_id = 10
    cookie_string = "magic-fake-cookie-string"

    responses.add(
        responses.POST,
        settings.FUGA_API_URL + "login",
        headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
        status=200,
    )
    responses.add(
        responses.GET,
        settings.FUGA_API_URL + "v2/artists/%s/identifier" % fuga_artist_id,
        json=json.load(load_fixture("FugaArtistIdentifier.json")),
        status=200,
    )
    artist_identifiers = FugaAPIClient().get_artist_identifier(fuga_artist_id)
    assert len(artist_identifiers) == 2
    assert artist_identifiers[0]["identifier"] == "spotify:artist:identifier"
    assert artist_identifiers[0]["issuingOrganization"]["name"] == "Spotify"
    assert artist_identifiers[1]["identifier"] == "1122334455"
    assert artist_identifiers[1]["issuingOrganization"]["name"] == "Apple Music"


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_fuga_post_delivery_takedown():
    fuga_id = 333
    fuga_store_id = 103731
    fuga_store_ids = [fuga_store_id]
    cookie_string = "magic-fake-cookie-string"

    responses.add(
        responses.POST,
        settings.FUGA_API_URL + "login",
        headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
        status=200,
    )
    responses.add(
        responses.POST,
        settings.FUGA_API_URL
        + "v2/products/%s/delivery_instructions/takedown" % fuga_id,
        json=json.load(load_fixture("FugaDeliveryInstructionsTakedown.json")),
        status=200,
    )

    response = FugaAPIClient().post_product_takedown(fuga_id, fuga_store_ids)

    takedown_instruction = None
    for delivery_instruction in response["delivery_instructions"]:
        if delivery_instruction["dsp"]["id"] == fuga_store_id:
            takedown_instruction = delivery_instruction

    assert takedown_instruction["state"] == "PROCESSING"
    assert takedown_instruction["action"] == "TAKEDOWN"


@responses.activate
@override_settings(
    FUGA_API_URL="https://fake.url/", FUGA_API_USER="test", FUGA_API_PASSWORD="test"
)
def test_fuga_post_delivery_deliver():
    fuga_id = 333
    fuga_store_id = 103731
    fuga_store_ids = [fuga_store_id]
    cookie_string = "magic-fake-cookie-string"

    responses.add(
        responses.POST,
        settings.FUGA_API_URL + "login",
        headers={"Set-Cookie": "connect.sid=%s;" % cookie_string},
        status=200,
    )
    responses.add(
        responses.POST,
        settings.FUGA_API_URL
        + "v2/products/%s/delivery_instructions/deliver" % fuga_id,
        json=json.load(load_fixture("FugaDeliveryInstructionsDeliver.json")),
        status=200,
    )

    response = FugaAPIClient().post_product_deliver(fuga_id, fuga_store_ids)

    takedown_instruction = None
    for delivery_instruction in response["delivery_instructions"]:
        if delivery_instruction["dsp"]["id"] == fuga_store_id:
            takedown_instruction = delivery_instruction

    assert takedown_instruction["state"] == "PROCESSING"
    assert takedown_instruction["action"] == "DELIVER"
