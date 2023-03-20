import pytest
from decimal import Decimal
from unittest import mock, skip

import phonenumbers
import responses
from django.db import connection
from django.conf import settings
from django.test import TestCase
from storages.backends.s3boto3 import S3Boto3StorageFile
from users.tests.factories import UserFactory
from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.utils import MapPgResults
from django.core.cache import cache
from amuse.cache import AmuseDatabaseCache
from django.test.utils import override_settings
from waffle.testutils import override_switch
from django.test.client import RequestFactory

from amuse.utils import (
    CLIENT_ANDROID,
    CLIENT_IOS,
    CLIENT_OTHER,
    CLIENT_WEB,
    convert_to_positive_and_round,
    download_to_bucket,
    format_phonenumber,
    FakePhoneNumberError,
    InvalidPhoneNumberError,
    log_func,
    match_strings,
    parse_client_version,
    parsed_django_request_string,
    rename_key,
    resolve_naming_conflicts,
    generate_password_reset_url,
    phone_region_code_from_number,
    parseJSONField,
    is_verify_phone_mismatch_country_blocked,
    get_client_captcha_token,
    check_swedish_pnr,
)


class DownloadToBucketTestCase(TestCase):
    @responses.activate
    def test_download_to_bucket(self):
        url = 'http://test-url'
        headers = {'Autorization': 'Bearer 123454'}
        data = b'abc123' * 666
        responses.add(method='GET', url=url, body=data)
        with mock.patch.object(S3Boto3StorageFile, 'write') as mocked_s3_write:
            download_to_bucket(
                url, settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME, 'filename', headers
            )
        # All data should've been written at once
        mocked_s3_write.assert_called_with(data)

    @responses.activate
    def test_download_to_bucket_chunked(self):
        url = 'http://test-url'
        headers = {'Autorization': 'Bearer 123454'}
        # Chunk encoded data
        data = '5\r\n' 'These\r\n' '3\r\n' 'Are\r\n' '6\r\n' 'Chunks\r\n' '0\r\n' '\r\n'

        # Add some attributes that urllib3.response wants for chunk streaming to be
        # possible
        original_get_response = responses.Response.get_response

        def mocked_get_response(self, request):
            response = original_get_response(self, request)
            response._fp.fp = response._fp
            response._fp._safe_read = response._fp.read
            response._original_response._method = 'GET'
            return response

        with mock.patch(
            'responses.Response.get_response', mocked_get_response
        ), mock.patch.object(S3Boto3StorageFile, 'write') as mocked_s3_write:
            responses.add(
                method='GET',
                url=url,
                body=data,
                stream=True,
                headers={'Transfer-Encoding': 'chunked'},
            )
            download_to_bucket(
                url, settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME, 'filename', headers
            )
        # Assert chunking works
        mocked_s3_write.assert_has_calls(
            [mock.call(b'These'), mock.call(b'Are'), mock.call(b'Chunks')]
        )


class FormatPhoneNumberTest(TestCase):
    def test_valid_phonenumber_is_allowed(self):
        assert format_phonenumber('+46704554090', 'SE') == '+46704554090'
        assert format_phonenumber('0704554090', 'SE') == '+46704554090'
        assert format_phonenumber('+46-70-455-40-90', 'SE') == '+46704554090'
        assert format_phonenumber('+46 70 455 40 90', 'SE') == '+46704554090'
        assert format_phonenumber('+1-202-555-0168', 'US') == '+12025550168'
        assert format_phonenumber('(1) 202-555-0168', 'US') == '+12025550168'
        assert format_phonenumber('+33785551551', 'FR') == '+33785551551'

        # Countrycode mismatch is overridden by phone number countrycode
        assert format_phonenumber('+46704554090', 'US') == '+46704554090'

    def test_invalid_phonenumber_is_not_allowed(self):
        with pytest.raises(InvalidPhoneNumberError):
            format_phonenumber('', 'SE')

        with pytest.raises(FakePhoneNumberError):
            format_phonenumber('55555', 'SE')


class ParseClientTestCase(TestCase):
    def test_parse_client_version_clients(self):
        user_agent_android = 'amuse-android/1.2.3;'
        user_agent_ios = 'amuse-ios/1.2.3;'
        user_agent_web = 'amuse-web/1.2.3;'
        user_agent_other = '...'
        self.assertEqual(CLIENT_ANDROID, parse_client_version(user_agent_android)[0])
        self.assertEqual(CLIENT_IOS, parse_client_version(user_agent_ios)[0])
        self.assertEqual(CLIENT_WEB, parse_client_version(user_agent_web)[0])
        self.assertEqual(CLIENT_OTHER, parse_client_version(user_agent_other)[0])

    def test_parse_client_version_versions(self):
        user_agent1 = 'amuse-android/0.0.0;'
        user_agent2 = 'amuse-ios/foo-bar-baz;'
        user_agent3 = 'amuse-web/abc123def456;'
        user_agent4 = 'foo-bar/1.2.3;'
        self.assertEqual('0.0.0', parse_client_version(user_agent1)[1])
        self.assertEqual('foo-bar-baz', parse_client_version(user_agent2)[1])
        self.assertEqual('abc123def456', parse_client_version(user_agent3)[1])
        self.assertEqual('N/A', parse_client_version(user_agent4)[1])

    def test_parse_client_version_ignorecase(self):
        user_agent1 = 'AMUSE-ios/1;'
        user_agent2 = 'AmUsE-ANDRoid/ABC;'
        self.assertEqual(CLIENT_IOS, parse_client_version(user_agent1)[0])
        self.assertEqual(CLIENT_ANDROID, parse_client_version(user_agent2)[0])


class TestConvertPositiveAndRound(TestCase):
    def test_rounds_half_up(self):
        assert convert_to_positive_and_round(Decimal('0.996')) == Decimal('1.0')
        assert convert_to_positive_and_round(Decimal('0.995')) == Decimal('1.0')
        assert convert_to_positive_and_round(Decimal('0.994')) == Decimal('0.99')


class TestStringMatching(TestCase):
    def setUp(self):
        self.s1 = "Mister Writer"
        self.s2 = "mister writer"
        self.s3 = "mister       writer"
        self.s4 = "miser    writer"
        self.s5 = "MISER WRITE"
        self.s6 = "Bugs Bunny"
        self.s7 = None

    def test_match_strings(self):
        self.assertTrue(match_strings(self.s1, self.s2))
        self.assertTrue(match_strings(self.s1, self.s3))
        self.assertTrue(match_strings(self.s1, self.s4))
        self.assertTrue(match_strings(self.s1, self.s5))
        self.assertFalse(match_strings(self.s1, self.s6))
        self.assertFalse(match_strings(self.s1, self.s7))


class TestMapPgResults(AmuseAPITestCase):
    def setUp(self):
        for i in range(0, 5):
            UserFactory(artist_name="UserName#%s" % i)

    def test_resultmapper(self):
        cursor = connection.cursor()
        cursor.execute("select * from users_user limit 5")
        results = cursor.fetchall()
        data = [MapPgResults(cursor, r) for r in results]
        self.assertEqual(len(data), 5)
        for d in data:
            self.assertIsInstance(d, MapPgResults)
            self.assertTrue(hasattr(d, 'id'))
            self.assertTrue(hasattr(d, 'email'))
            self.assertTrue(hasattr(d, 'first_name'))
            self.assertTrue(hasattr(d, 'last_name'))
            self.assertTrue(hasattr(d, 'is_active'))
            self.assertTrue(hasattr(d, 'created'))
            self.assertTrue(hasattr(d, 'country'))


class LogFuncTestCase(TestCase):
    @skip
    def test_log_func_truncates_values(self):
        @log_func(max_length=10)
        def foo(*arg, **kwargs):
            return arg

        arg = "".join(["abc" for _ in range(100)])
        kwarg = {"1": "".join(["abc" for _ in range(100)])}

        with self.assertLogs(logger="amuse") as log:
            foo(arg, **kwarg)

        log_1 = "INFO:amuse:Start foo(args=('abcabca…, kwargs={'1': 'ab…)"
        log_2 = "INFO:amuse:End foo with return value ('abcabca…"

        assert log.output[0] == log_1
        assert log.output[1] == log_2


class DjangoRedisCache(AmuseAPITestCase):
    def setUp(self):
        self.users = []
        for i in range(0, 5):
            self.users.append(UserFactory(artist_name="UserName#%s" % i))

    def test_djanog_cache(self):
        cache.set('test', self.users)
        data = cache.get('test')
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 5)


@pytest.mark.parametrize(
    'data,old_key,new_key,expected_data',
    [
        (
            {
                'id': 6,
                'rate': Decimal('0.5000'),
                'status': 1,
                'artist_name': 'Gassito',
                'song_name': 'ReleaseAndroid001',
                'song_isrc': 'GBSMU7491306',
                'cover_art': '//s3-dev.amuse.io:9000/amuse-cover-art-uploaded-dev/cover.800x800.jpg',
            },
            'cover_art',
            'cover_art_url',
            {
                'id': 6,
                'rate': Decimal('0.5000'),
                'status': 1,
                'artist_name': 'Gassito',
                'song_name': 'ReleaseAndroid001',
                'song_isrc': 'GBSMU7491306',
                'cover_art_url': '//s3-dev.amuse.io:9000/amuse-cover-art-uploaded-dev/cover.800x800.jpg',
            },
        ),
        (
            {
                'id': 1,
                'auth_token': '[Filtered]',
                'first_name': 'Ghassen',
                'last_name': 'Telmoudi',
                'artist_name': 'Gas',
                'email': 'example@amuse.io',
                'email_verified': True,
                'category': 'priority',
                'phone': '+46723732765',
                'country': 'TN',
                'language': None,
                'facebook_id': None,
                'google_id': None,
                'profile_link': None,
                'profile_photo': None,
                'spotify_id': None,
                'spotify_page': None,
                'spotify_image': None,
                'twitter_name': None,
                'facebook_page': None,
                'instagram_name': None,
                'soundcloud_page': None,
                'youtube_channel': None,
                'firebase_token': '[Filtered]',
                'newsletter': False,
                'is_pro': True,
                'created': '2020-01-24T14:33:09.159545Z',
                'main_artist_profile': None,
            },
            'country',
            'country_code',
            {
                'id': 1,
                'auth_token': '[Filtered]',
                'first_name': 'Ghassen',
                'last_name': 'Telmoudi',
                'artist_name': 'Gas',
                'email': 'example@amuse.io',
                'email_verified': True,
                'category': 'priority',
                'phone': '+46723732765',
                'country_code': 'TN',
                'language': None,
                'facebook_id': None,
                'google_id': None,
                'profile_link': None,
                'profile_photo': None,
                'spotify_id': None,
                'spotify_page': None,
                'spotify_image': None,
                'twitter_name': None,
                'facebook_page': None,
                'instagram_name': None,
                'soundcloud_page': None,
                'youtube_channel': None,
                'firebase_token': '[Filtered]',
                'newsletter': False,
                'is_pro': True,
                'created': '2020-01-24T14:33:09.159545Z',
                'main_artist_profile': None,
            },
        ),
        (
            {
                'id': 1,
                'name': 'Gas',
                'created': '2020-01-24T14:45:15.603616Z',
                'spotify_page': None,
                'twitter_name': None,
                'facebook_page': None,
                'instagram_name': None,
                'soundcloud_page': None,
                'youtube_channel': None,
                'spotify_id': None,
                'spotify_image': None,
                'apple_id': None,
                'has_owner': True,
                'role': 'admin',
                'releases_count': 5,
                'owner': {
                    'id': 1,
                    'first_name': 'Ghassen',
                    'last_name': 'Telmoudi',
                    'profile_photo': None,
                },
                'main_artist_profile': False,
            },
            'main_artist_profile',
            'is_main_artist_profile',
            {
                'id': 1,
                'name': 'Gas',
                'created': '2020-01-24T14:45:15.603616Z',
                'spotify_page': None,
                'twitter_name': None,
                'facebook_page': None,
                'instagram_name': None,
                'soundcloud_page': None,
                'youtube_channel': None,
                'spotify_id': None,
                'spotify_image': None,
                'apple_id': None,
                'has_owner': True,
                'role': 'admin',
                'releases_count': 5,
                'owner': {
                    'id': 1,
                    'first_name': 'Ghassen',
                    'last_name': 'Telmoudi',
                    'profile_photo': None,
                },
                'is_main_artist_profile': False,
            },
        ),
    ],
)
def test_rename_key(data, old_key, new_key, expected_data):
    assert rename_key(data, old_key, new_key) == expected_data


@pytest.mark.parametrize(
    'uri,method,response',
    [
        ('/any_url', 'GET', {}),
        ('/any_url', 'POST', {}),
        ('/users', 'POST', {}),
        ('/artists', 'POST', {}),
        ('/royalty-splits', 'POST', {}),
        ('/users/1/transactions/', 'GET', {}),
        ('/artists/1/team/', 'GET', {}),
        ('/royalty-splits/release/1/', 'GET', {}),
        ('/royalty-splits', 'GET', {'detail': 'Something went wrong'}),
        ('/users', 'GET', {'detail': 'Something went wrong'}),
        ('/artists', 'GET', {'detail': 'Something went wrong'}),
    ],
)
@mock.patch('amuse.utils.rename_key')
def test_resolve_naming_conflicts_doesnt_call_rename_key(
    mocked_rename_key, uri, method, response
):
    mocked_record = mock.Mock()
    mocked_record.uri = uri
    mocked_record.method = method
    mocked_record.response = response
    resolve_naming_conflicts(mocked_record)
    assert not mocked_rename_key.called


@pytest.mark.parametrize(
    'uri,method,response,old_key,new_key',
    [
        (
            '/users/1/',
            'GET',
            {
                'id': 1,
                'auth_token': '[Filtered]',
                'first_name': 'Ghassen',
                'last_name': 'Telmoudi',
                'artist_name': 'Gas',
                'email': 'example@amuse.io',
                'email_verified': True,
                'category': 'priority',
                'phone': '+46723732765',
                'country': 'TN',
                'language': None,
                'facebook_id': None,
                'google_id': None,
                'profile_link': None,
                'profile_photo': None,
                'spotify_id': None,
                'spotify_page': None,
                'spotify_image': None,
                'twitter_name': None,
                'facebook_page': None,
                'instagram_name': None,
                'soundcloud_page': None,
                'youtube_channel': None,
                'firebase_token': '[Filtered]',
                'newsletter': False,
                'is_pro': True,
                'created': '2020-01-24T14:33:09.159545Z',
                'main_artist_profile': None,
            },
            'country',
            'country_code',
        ),
        (
            '/artists/',
            'GET',
            [
                {
                    'id': 1,
                    'name': 'Gas',
                    'created': '2020-01-24T14:45:15.603616Z',
                    'spotify_page': None,
                    'twitter_name': None,
                    'facebook_page': None,
                    'instagram_name': None,
                    'soundcloud_page': None,
                    'youtube_channel': None,
                    'spotify_id': None,
                    'spotify_image': None,
                    'apple_id': None,
                    'has_owner': True,
                    'role': 'admin',
                    'releases_count': 5,
                    'owner': {
                        'id': 1,
                        'first_name': 'Ghassen',
                        'last_name': 'Telmoudi',
                        'profile_photo': None,
                    },
                    'main_artist_profile': False,
                }
            ],
            'main_artist_profile',
            'is_main_artist_profile',
        ),
        (
            '/artists/',
            'POST',
            [
                {
                    'apple_id': None,
                    'created': '2020-07-27T10:13:58.737478Z',
                    'facebook_page': None,
                    'has_owner': True,
                    'id': 1869236,
                    'instagram_name': None,
                    'main_artist_profile': False,
                    'name': 'Fanze',
                    'owner': {
                        'first_name': 'Yusuf S.',
                        'id': 811403,
                        'last_name': 'Tarhan',
                        'profile_photo': None,
                    },
                    'releases_count': 0,
                    'role': 'owner',
                    'soundcloud_page': None,
                    'spotify_id': None,
                    'spotify_image': None,
                    'spotify_page': None,
                    'twitter_name': None,
                    'youtube_channel': None,
                }
            ],
            'main_artist_profile',
            'is_main_artist_profile',
        ),
        (
            '/artists/1/',
            'GET',
            {
                'id': 1,
                'name': 'Gas',
                'created': '2020-01-24T14:45:15.603616Z',
                'spotify_page': None,
                'twitter_name': None,
                'facebook_page': None,
                'instagram_name': None,
                'soundcloud_page': None,
                'youtube_channel': None,
                'spotify_id': None,
                'spotify_image': None,
                'apple_id': None,
                'has_owner': True,
                'role': 'admin',
                'releases_count': 5,
                'owner': {
                    'id': 1,
                    'first_name': 'Ghassen',
                    'last_name': 'Telmoudi',
                    'profile_photo': None,
                },
                'main_artist_profile': False,
            },
            'main_artist_profile',
            'is_main_artist_profile',
        ),
        (
            '/royalty-splits',
            'GET',
            [
                {
                    'id': 6,
                    'rate': Decimal('0.5000'),
                    'status': 1,
                    'artist_name': 'Gassito',
                    'song_name': 'ReleaseAndroid001',
                    'song_isrc': 'GBSMU7491306',
                    'cover_art': '//s3-dev.amuse.io:9000/amuse-cover-art-uploaded-dev/cover.800x800.jpg',
                }
            ],
            'cover_art',
            'cover_art_url',
        ),
        (
            '/artists/313969/social_media/',
            'POST',
            {
                'apple_id': None,
                'created': '2019-05-15T07:46:53.597634Z',
                'facebook_page': 'https://www.facebook.com/siroka2000/',
                'has_owner': True,
                'id': 313969,
                'instagram_name': 'https://instagram.com/stories/acs_s4y/218483965936',
                'main_artist_profile': False,
                'name': 'SirOka',
                'owner': {
                    'first_name': 'Sir',
                    'id': 314974,
                    'last_name': 'Oka',
                    'profile_photo': 'https://amuse-profile-photo.s3.amazonaws.com:443/b51a27dc-0459-4c3b-a1b3-bcefa611d067.jpg',
                },
                'releases_count': 7,
                'role': 'owner',
                'soundcloud_page': 'https://soundcloud.com/seroka2000',
                'spotify_id': None,
                'spotify_image': None,
                'spotify_page': 'https://open.spotify.com/album/4rkmI3WHpbRG1JMtPLdelJ',
                'twitter_name': 'https://twitter.com/seroka4_you?s=09',
                'youtube_channel': 'https://www.youtube.com/channel/ucdqv5yemu_aiud3nt',
            },
            'main_artist_profile',
            'is_main_artist_profile',
        ),
        (
            '/releases/',
            'GET',
            [
                {
                    'artist_roles': [
                        {
                            'artist_id': 1624633,
                            'artist_name': 'Jafeth Perez',
                            'role': 'primary_artist',
                        }
                    ],
                    'cover_art': {
                        'checksum': '6d338b71974aaa8d7ce8c83e5af5452d',
                        'file': 'https://cdn.amuse.io/8d9b4ccd-cd2a-4084-b15c-f25fe4180d69.jpg',
                        'filename': '8d9b4ccd-cd2a-4084-b15c-f25fe4180d69.jpg',
                        'id': 831711,
                        'thumbnail': 'https://cdn.amuse.io/8d9b4ccd-cd2a-4084-b15c-f25fe4180d69.400x400.jpg',
                    },
                    'created': '2020-06-09T00:33:05.810601Z',
                    'error_flags': {
                        'artwork_blurry': False,
                        'artwork_format': False,
                        'artwork_generic': False,
                        'artwork_logos-brands': False,
                        'artwork_pa-logo-mismatch': False,
                        'artwork_primary-or-featured': False,
                        'artwork_size': False,
                        'artwork_size-new': False,
                        'artwork_social-media': False,
                        'artwork_text': False,
                        'compound-artist': False,
                        'explicit_parental-advisory': False,
                        'metadata_generic-terms': False,
                        'metadata_symbols-emoji-info': False,
                        'metadata_symbols-or-emoji': False,
                        'release_date-changed': False,
                        'release_duplicate': False,
                        'release_generic-artist-name': False,
                        'release_misleading-artist-name': False,
                        'release_underage': False,
                        'rights_no-rights': False,
                        'titles_differs': False,
                    },
                    'excluded_countries': [],
                    'excluded_stores': [3, 35, 51, 48, 41, 36, 12, 5, 4],
                    'genre': {'id': 15, 'name': 'Latin'},
                    'id': 760190,
                    'label': None,
                    'name': 'Tu Mano',
                    'original_release_date': None,
                    'release_date': '2020-06-24',
                    'songs': [
                        {
                            'artists_invites': [],
                            'artists_roles': [
                                {
                                    'artist_id': 1624633,
                                    'artist_name': 'Jafeth Perez',
                                    'roles': ['primary_artist'],
                                },
                                {
                                    'artist_id': 1624613,
                                    'artist_name': 'Jafeth  Perez',
                                    'roles': ['writer'],
                                },
                            ],
                            'cover_licensor': '',
                            'error_flags': {
                                'audio_bad-quality': False,
                                'audio_continuous-mix': False,
                                'audio_cut-short': False,
                                'audio_silent-end-beginning': False,
                                'audio_too-short': False,
                                'explicit_lyrics': False,
                                'genre_not-approved': False,
                                'misleading-artist-name': False,
                                'rights_no-rights': False,
                                'rights_remix': False,
                                'rights_samplings': False,
                                'wrong-isrc': False,
                            },
                            'explicit': 'none',
                            'filename': 'JAFETH SIEMPRE CANTARE.wav',
                            'genre': {'id': 15, 'name': 'Latin'},
                            'id': 1852264,
                            'isrc': 'SE6I32053990',
                            'name': 'Tu Mano',
                            'origin': 'original',
                            'original_release_date': None,
                            'preview_start_time': 99,
                            'recording_year': 2020,
                            'royalty_splits': [
                                {
                                    'name': 'Jafeth Perez',
                                    'photo': 'https://amuse-profile-photo.s3.amazonaws.com:443/7e8199df-cbf8-429c-97d0-672dd8257dea.png',
                                    'rate': 1,
                                }
                            ],
                            'sequence': 1,
                            'version': None,
                            'youtube_content_id': 'none',
                        }
                    ],
                    'status': 'released',
                    'type': 'single',
                    'upc': '0707856460902',
                    'user_id': 745765,
                }
            ],
            'status',
            'status_string',
        ),
        (
            '/releases/101881/',
            'GET',
            {
                'artist_roles': [
                    {
                        'artist_id': 279404,
                        'artist_name': 'Ghassen',
                        'role': 'primary_artist',
                    }
                ],
                'cover_art': {
                    'checksum': 'ea74f0a828ff41af57ce446b343d71f4',
                    'file': 'https://cdn-staging.amuse.io/cover.jpg',
                    'filename': 'cover.jpg',
                    'id': 172022,
                    'thumbnail': 'https://cdn-staging.amuse.io/cover.400x400.jpg',
                },
                'created': '2020-07-28T17:37:57.396036Z',
                'error_flags': {
                    'artwork_blurry': False,
                    'artwork_format': False,
                    'artwork_generic': False,
                    'artwork_logos-brands': False,
                    'artwork_pa-logo-mismatch': False,
                    'artwork_primary-or-featured': False,
                    'artwork_size': False,
                    'artwork_size-new': False,
                    'artwork_social-media': False,
                    'artwork_text': False,
                    'compound-artist': False,
                    'explicit_parental-advisory': False,
                    'metadata_generic-terms': False,
                    'metadata_symbols-emoji-info': False,
                    'metadata_symbols-or-emoji': False,
                    'release_date-changed': False,
                    'release_duplicate': False,
                    'release_generic-artist-name': False,
                    'release_misleading-artist-name': False,
                    'release_underage': False,
                    'rights_no-rights': False,
                    'titles_differs': False,
                },
                'excluded_countries': ['NO', 'DK'],
                'excluded_stores': [45, 41, 44, 43, 18],
                'genre': {'id': 1, 'name': 'Alternative'},
                'id': 101881,
                'label': 'Ghassen',
                'name': 'Postman Release V4',
                'original_release_date': None,
                'release_date': '2020-09-11',
                'songs': [
                    {
                        'artists_invites': [],
                        'artists_roles': [
                            {
                                'artist_id': 280662,
                                'artist_name': 'Iteration1',
                                'roles': [
                                    'primary_artist',
                                    'writer',
                                    'producer',
                                    'mixer',
                                ],
                            },
                            {
                                'artist_id': 3,
                                'artist_name': 'Dhat Gyal',
                                'roles': ['featured_artist'],
                            },
                        ],
                        'cover_licensor': '',
                        'error_flags': {
                            'audio_bad-quality': False,
                            'audio_continuous-mix': False,
                            'audio_cut-short': False,
                            'audio_silent-end-beginning': False,
                            'audio_too-short': False,
                            'explicit_lyrics': False,
                            'genre_not-approved': False,
                            'misleading-artist-name': False,
                            'rights_no-rights': False,
                            'rights_remix': False,
                            'rights_samplings': False,
                            'wrong-isrc': False,
                        },
                        'explicit': 'clean',
                        'filename': 'users_filename.wav',
                        'genre': {'id': 1, 'name': 'Alternative'},
                        'id': 238471,
                        'isrc': 'QZBJV1847115',
                        'name': 'Test Song 1',
                        'origin': 'remix',
                        'original_release_date': None,
                        'preview_start_time': 0,
                        'recording_year': 2018,
                        'royalty_splits': [],
                        'sequence': 1,
                        'version': 'Version Title',
                        'youtube_content_id': 'none',
                    }
                ],
                'status': 'pending_approval',
                'type': 'single',
                'upc': '-',
                'user_id': 139872,
            },
            'status',
            'status_string',
        ),
        (
            '/releases/101881/',
            'PATCH',
            {
                'artist_roles': [
                    {
                        'artist_id': 279404,
                        'artist_name': 'Ghassen',
                        'role': 'primary_artist',
                    }
                ],
                'cover_art': {
                    'checksum': 'ea74f0a828ff41af57ce446b343d71f4',
                    'file': 'https://cdn-staging.amuse.io/cover.jpg',
                    'filename': 'cover.jpg',
                    'id': 172022,
                    'thumbnail': 'https://cdn-staging.amuse.io/cover.400x400.jpg',
                },
                'created': '2020-07-28T17:37:57.396036Z',
                'error_flags': {
                    'artwork_blurry': False,
                    'artwork_format': False,
                    'artwork_generic': False,
                    'artwork_logos-brands': False,
                    'artwork_pa-logo-mismatch': False,
                    'artwork_primary-or-featured': False,
                    'artwork_size': False,
                    'artwork_size-new': False,
                    'artwork_social-media': False,
                    'artwork_text': False,
                    'compound-artist': False,
                    'explicit_parental-advisory': False,
                    'metadata_generic-terms': False,
                    'metadata_symbols-emoji-info': False,
                    'metadata_symbols-or-emoji': False,
                    'release_date-changed': False,
                    'release_duplicate': False,
                    'release_generic-artist-name': False,
                    'release_misleading-artist-name': False,
                    'release_underage': False,
                    'rights_no-rights': False,
                    'titles_differs': False,
                },
                'excluded_countries': ['NO', 'DK'],
                'excluded_stores': [45, 41, 44, 43, 18],
                'genre': {'id': 1, 'name': 'Alternative'},
                'id': 101881,
                'label': 'Ghassen',
                'name': 'Postman Release V4',
                'original_release_date': None,
                'release_date': '2020-09-11',
                'songs': [
                    {
                        'artists_invites': [],
                        'artists_roles': [
                            {
                                'artist_id': 280662,
                                'artist_name': 'Iteration1',
                                'roles': [
                                    'primary_artist',
                                    'writer',
                                    'producer',
                                    'mixer',
                                ],
                            },
                            {
                                'artist_id': 3,
                                'artist_name': 'Dhat Gyal',
                                'roles': ['featured_artist'],
                            },
                        ],
                        'cover_licensor': '',
                        'error_flags': {
                            'audio_bad-quality': False,
                            'audio_continuous-mix': False,
                            'audio_cut-short': False,
                            'audio_silent-end-beginning': False,
                            'audio_too-short': False,
                            'explicit_lyrics': False,
                            'genre_not-approved': False,
                            'misleading-artist-name': False,
                            'rights_no-rights': False,
                            'rights_remix': False,
                            'rights_samplings': False,
                            'wrong-isrc': False,
                        },
                        'explicit': 'clean',
                        'filename': 'users_filename.wav',
                        'genre': {'id': 1, 'name': 'Alternative'},
                        'id': 238471,
                        'isrc': 'QZBJV1847115',
                        'name': 'Test Song 1',
                        'origin': 'remix',
                        'original_release_date': None,
                        'preview_start_time': 0,
                        'recording_year': 2018,
                        'royalty_splits': [],
                        'sequence': 1,
                        'version': 'Version Title',
                        'youtube_content_id': 'none',
                    }
                ],
                'status': 'pending_approval',
                'type': 'single',
                'upc': '-',
                'user_id': 139872,
            },
            'status',
            'status_string',
        ),
        (
            '/releases/',
            'POST',
            {
                'artist_roles': [
                    {
                        'artist_id': 279404,
                        'artist_name': 'Ghassen',
                        'role': 'primary_artist',
                    }
                ],
                'cover_art': {
                    'checksum': 'ea74f0a828ff41af57ce446b343d71f4',
                    'file': 'https://cdn-staging.amuse.io/cover.jpg',
                    'filename': 'cover.jpg',
                    'id': 172022,
                    'thumbnail': 'https://cdn-staging.amuse.io/cover.400x400.jpg',
                },
                'created': '2020-07-28T17:37:57.396036Z',
                'error_flags': {
                    'artwork_blurry': False,
                    'artwork_format': False,
                    'artwork_generic': False,
                    'artwork_logos-brands': False,
                    'artwork_pa-logo-mismatch': False,
                    'artwork_primary-or-featured': False,
                    'artwork_size': False,
                    'artwork_size-new': False,
                    'artwork_social-media': False,
                    'artwork_text': False,
                    'compound-artist': False,
                    'explicit_parental-advisory': False,
                    'metadata_generic-terms': False,
                    'metadata_symbols-emoji-info': False,
                    'metadata_symbols-or-emoji': False,
                    'release_date-changed': False,
                    'release_duplicate': False,
                    'release_generic-artist-name': False,
                    'release_misleading-artist-name': False,
                    'release_underage': False,
                    'rights_no-rights': False,
                    'titles_differs': False,
                },
                'excluded_countries': ['NO', 'DK'],
                'excluded_stores': [45, 41, 44, 43, 18],
                'genre': {'id': 1, 'name': 'Alternative'},
                'id': 101881,
                'label': 'Ghassen',
                'name': 'Postman Release V4',
                'original_release_date': None,
                'release_date': '2020-09-11',
                'songs': [
                    {
                        'artists_invites': [],
                        'artists_roles': [
                            {
                                'artist_id': 280662,
                                'artist_name': 'Iteration1',
                                'roles': [
                                    'primary_artist',
                                    'writer',
                                    'producer',
                                    'mixer',
                                ],
                            },
                            {
                                'artist_id': 3,
                                'artist_name': 'Dhat Gyal',
                                'roles': ['featured_artist'],
                            },
                        ],
                        'cover_licensor': '',
                        'error_flags': {
                            'audio_bad-quality': False,
                            'audio_continuous-mix': False,
                            'audio_cut-short': False,
                            'audio_silent-end-beginning': False,
                            'audio_too-short': False,
                            'explicit_lyrics': False,
                            'genre_not-approved': False,
                            'misleading-artist-name': False,
                            'rights_no-rights': False,
                            'rights_remix': False,
                            'rights_samplings': False,
                            'wrong-isrc': False,
                        },
                        'explicit': 'clean',
                        'filename': 'users_filename.wav',
                        'genre': {'id': 1, 'name': 'Alternative'},
                        'id': 238471,
                        'isrc': 'QZBJV1847115',
                        'name': 'Test Song 1',
                        'origin': 'remix',
                        'original_release_date': None,
                        'preview_start_time': 0,
                        'recording_year': 2018,
                        'royalty_splits': [],
                        'sequence': 1,
                        'version': 'Version Title',
                        'youtube_content_id': 'none',
                    }
                ],
                'status': 'pending_approval',
                'type': 'single',
                'upc': '-',
                'user_id': 139872,
            },
            'status',
            'status_string',
        ),
    ],
)
@mock.patch('amuse.utils.rename_key')
def test_resolve_naming_conflicts_calls_rename_key(
    mocked_rename_key, uri, method, response, old_key, new_key
):
    mocked_record = mock.Mock()
    mocked_record.uri = uri
    mocked_record.method = method
    mocked_record.response = response
    resolve_naming_conflicts(mocked_record)
    if isinstance(response, list):
        response = response[0]
    mocked_rename_key.assert_called_once_with(response, old_key, new_key)


def test_parsed_django_request_string():
    django_request_string = "<WSGIRequest: GET '/subscriptions/current/'>"
    expected_data = {'method': 'GET', 'request_url': '/subscriptions/current/'}
    assert expected_data == parsed_django_request_string(django_request_string)


@pytest.mark.django_db
@mock.patch("amuse.utils.parse_client_data", return_value={"country": "XX"})
@mock.patch("amuse.utils.phone_region_code_from_number", return_value="XX")
def test_is_verify_phone_mismatch_country_blocked(mock_1, mock_2):
    # test with no active switch
    assert is_verify_phone_mismatch_country_blocked(mock.Mock()) == False

    # test with active switch and mismatching country codes
    with override_switch("sinch:block-mismatch:xx", True):
        mock_2.return_value = {"country": "SE"}
        assert is_verify_phone_mismatch_country_blocked(mock.Mock()) == True

    # test with active switch and matching country codes
    with override_switch("sinch:block-mismatch:us", True):
        mock_1.return_value = "US"
        mock_2.return_value = {"country": "US"}
        assert is_verify_phone_mismatch_country_blocked(mock.Mock()) == False


class GeneratePasswordResetURLtestCase(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        # . Fixed pk for deterministic uid obfuscation.
        self.user = UserFactory(country='US', pk=4_125_512)

    @mock.patch(
        'amuse.mails.password_reset_token_generator.make_token',
        return_value='5il-e6dd47c90464b588d4cc',
    )
    def test_generate_password_reset_url(self, mock_generator):
        url = generate_password_reset_url(self.user)

        expected = 'http://app-dev.amuse.io/password-reset/NDEyNTUxMg/5il-e6dd47c90464b588d4cc/'
        self.assertEqual(expected, url)


def test_phone_region_code_from_number_valid_number_returns_valid_region_code():
    country_code = phone_region_code_from_number("+46701234567")
    assert country_code == "SE"


def test_phone_region_code_from_number_invalid_number_returns_unknown_region():
    country_code = phone_region_code_from_number("+1")
    assert country_code == phonenumbers.phonenumberutil.UNKNOWN_REGION


def test_phone_region_code_from_number_unknown_number_returns_unknown_region():
    country_code = phone_region_code_from_number("+123")
    assert country_code == phonenumbers.phonenumberutil.UNKNOWN_REGION


def test_parseJSONfield():
    test_a = {"a": 1}
    test_b = '{"a":1}'
    assert parseJSONField(test_a) == test_a
    assert parseJSONField(test_b) == test_a


def patch_func(instance, target, mock_name):
    """
    Call this function in a setUp class to patch a function on all class methods

    Example:
        def setUp(self):
            patch_func(self, "amuse.tasks.blabla", "mocked_blabla")

        def method_a(self):
            # mocked_blabla is available in this scope
            pass
    """
    patcher = mock.patch(target)
    instance.addCleanup(patcher.stop)
    setattr(instance, mock_name, patcher.start())


class TestAmuseDatabaseCache(TestCase):
    @override_settings(
        CACHES={
            'default': {
                'BACKEND': 'amuse.cache.AmuseDatabaseCache',
                'LOCATION': 'django_cache',
            }
        }
    )
    def test_amuse_db_cache(self):
        from django.core.management import call_command

        call_command('createcachetable')
        cache.set('test', 10)
        data = cache.get('test')
        assert data == 10


def test_get_client_captcha_token():
    rf = RequestFactory()
    captcha_header = {settings.CAPTCHA_HEADER_KEY: 'asd124'}
    post_request = rf.post('/submit/', {'foo': 'bar'}, **captcha_header)
    token = get_client_captcha_token(post_request)
    assert token == 'asd124'

    post_request2 = rf.post(path='/submit/', data={settings.CAPTCHA_BODY_KEY: 'asd134'})
    token = get_client_captcha_token(request=post_request2, form=True)
    assert token == 'asd134'


@pytest.mark.parametrize(
    "pnr,expected",
    [
        ('19850811-1237', True),
        ('19850811-1234', False),
        ('8508111237', True),
        ('8508111234', False),
        ('198508111237', True),
        ('198508111234', False),
        ('8702141238', True),
        ('8702141234', False),
        ('19860930-1232', True),
        ('19860930-1234', False),
        ('abc', False),
        ('', False),
        ('123', False),
        ('1234567890', False),
        ('9999999999', False),
        ('0000000000', False),
        ('860521-2530', False),
        (None, False),
    ],
)
def test_check_swedish_pnr(pnr, expected):
    assert check_swedish_pnr(pnr) == expected
