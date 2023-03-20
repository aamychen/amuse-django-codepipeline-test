import json
import responses
from django.conf import settings
from django.test import TestCase, override_settings
from amuse.vendor.acrcloud.id import identify_song
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from releases.models.song import SongFile
from releases.tests.factories import SongFileFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class ACRCloudTestCase(TestCase):
    @responses.activate
    def test_not_identify_song(self):
        add_zendesk_mock_post_response()
        responses.add(
            responses.POST,
            settings.ACRCLOUD_ENDPOINT,
            json.dumps({'status': {'msg': '', 'code': 2004}}),
        )
        song_file = SongFileFactory(type=SongFile.TYPE_MP3, file__data=b'foo')
        identify_song(song_file.song)
        self.assertEqual(song_file.song.acrcloud_matches.count(), 0)

    @responses.activate
    def test_identify_song(self):
        add_zendesk_mock_post_response()
        response = {
            'status': {'msg': 'Success', 'code': 0},
            'metadata': {
                'music': [
                    {
                        'external_ids': {'isrc': 'TCABY1453125', 'upc': '859712948250'},
                        'play_offset_ms': 12720,
                        'title': 'My Wise Dome',
                        'external_metadata': {
                            'spotify': {
                                'album': {
                                    'name': 'Fatimah Patrice',
                                    'id': '5W4t4I4BTKq0yMj2sCCS1w',
                                },
                                'artists': [
                                    {
                                        'name': 'Fatimah Patrice',
                                        'id': '3lUt0yG1Rh4TlGZJTEMsPR',
                                    }
                                ],
                                'track': {
                                    'name': 'Heartz in Autumn',
                                    'id': '5T2fdfaMjUzL642H6FoX4j',
                                },
                            }
                        },
                        'artists': [{'name': 'Isaac Key-Ali'}],
                        'release_date': '2014-07-17',
                        'source': 'kkbox:PXUK8GXr8IwsBZXeyG',
                        'label': 'Fatimah Patrice',
                        'duration_ms': 178_880,
                        'album': {'name': 'L.E.a.D.E.R One E Pluribus Unam'},
                        'acrid': '898e068cccbd1bcaf95a08ad75a2ee50',
                        'result_from': 1,
                        'score': 100,
                    }
                ]
            },
        }
        responses.add(responses.POST, settings.ACRCLOUD_ENDPOINT, json.dumps(response))
        song_file = SongFileFactory(type=SongFile.TYPE_MP3, file__data=b'foo')
        identify_song(song_file.song)
        self.assertEqual(
            song_file.song.acrcloud_matches.count(), len(response['metadata']['music'])
        )
