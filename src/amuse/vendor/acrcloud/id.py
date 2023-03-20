import hmac
import os
import json
import requests
from base64 import b64encode
from hashlib import sha1
from time import time
from django.conf import settings
from amuse.models.acrcloud import ACRCloudMatch
from releases.utils import filter_song_file_mp3


def identify_song(song):
    response = identify_file(filter_song_file_mp3(song).file)
    if response['status']['code'] != 0:
        return
    if not len(response['metadata']['music']):
        return
    for match in response['metadata']['music']:
        acrcloud_match = ACRCloudMatch.objects.create(
            song=song,
            score=match['score'],
            offset=(match['play_offset_ms'] / 1000),
            artist_name=match['artists'][0]['name'],
            album_title=match['album']['name'],
            track_title=match['title'],
            match_upc=match['external_ids'].get('upc'),
            match_isrc=match['external_ids'].get('isrc'),
            external_metadata=match['external_metadata'],
        )


def identify_file(file):
    timestamp = time()
    string_to_sign = f"POST\n/v1/identify\n{settings.ACRCLOUD_ACCESS_KEY}\naudio\n1\n{str(timestamp)}"
    signature = b64encode(
        hmac.new(
            bytes(settings.ACRCLOUD_ACCESS_SECRET.encode()),
            bytes(string_to_sign.encode()),
            sha1,
        ).digest()
    )
    data = {
        'access_key': settings.ACRCLOUD_ACCESS_KEY,
        'sample_bytes': 1_000_000,
        'sample': b64encode(file.read(1_000_000)),
        'timestamp': str(timestamp),
        'signature': signature,
        'data_type': 'audio',
        'signature_version': '1',
    }
    return json.loads(requests.post(settings.ACRCLOUD_ENDPOINT, data).text)
