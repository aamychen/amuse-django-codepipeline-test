from unittest import mock
from django.urls import reverse
from rest_framework import status
import responses
from users.tests.factories import (
    UserFactory,
    UserMetadataFactory,
    Artistv2Factory,
    UserArtistRoleFactory,
)
from ..base import API_V6_ACCEPT_VALUE, AmuseAPITestCase
from amuse.storages import S3Storage
from django.conf import settings

from waffle.testutils import override_switch
from django.core.signing import get_cookie_signer
from amuse.tokens import otp_token_generator
from django.core.cache import cache
from users.models import User


class TestRegistrationAPIV6TestCase(AmuseAPITestCase):
    def tearDown(self) -> None:
        cache.clear()

    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.client.credentials(HTTP_ACCEPT=API_V6_ACCEPT_VALUE)
        bucket = S3Storage(
            bucket_name=settings.AWS_PROFILE_PHOTO_BUCKET_NAME, querystring_auth=False
        )

        self.keys = [
            'first_name',
            'last_name',
            'artist_name',
            'email',
            'phone',
            'country',
            'language',
            'facebook_id',
            'google_id',
            'profile_link',
            'profile_photo',
            'spotify_page',
            'twitter_name',
            'facebook_page',
            'instagram_name',
            'soundcloud_page',
            'youtube_channel',
            'firebase_token',
            'password',
            'newsletter',
            'spotify_id',
        ]

        user = UserFactory.build(first_name='Foo', last_name='Bar', country='US')
        profile_photo = user.profile_photo
        with bucket.open(profile_photo, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())

        self.data = {
            'facebook_access_token': '',
            'google_id_token': '',
            **{k: getattr(user, k, '') for k in self.keys},
        }

        self.user = user

    @responses.activate
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch(
        'amuse.api.v6.serializers.user.validate_phone', return_value='+38761234567'
    )
    def test_create_user(self, twilio_mock, zendesk_mock, fetch_mock):
        bucket = S3Storage(
            bucket_name=settings.AWS_PROFILE_PHOTO_BUCKET_NAME, querystring_auth=False
        )
        url = reverse('user-list')
        user = UserFactory.build(
            first_name='Foo', last_name='Bar', country='US', password='asd123qwe'
        )
        # Make sure the profile photo exists
        profile_photo = user.profile_photo
        with bucket.open(profile_photo, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())

        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'user_artist_role_token': None,
            'impact_click_id': 'impact123',
            **{k: getattr(user, k) for k in self.keys},
        }
        with override_switch('auth:v6:enabled', True):
            response = self.client.post(url, data, format='json')
            self.assertEqual(
                response.status_code, status.HTTP_201_CREATED, response.data
            )

            # asser user is created
            created_user = User.objects.get(id=response.data['id'])
            assert created_user is not None

            # Assert we set correct opt cookie in response
            otp_cookie = response.cookies.get(settings.OTP_COOKIE_NAME)
            otp_token = get_cookie_signer(salt=settings.OTP_COOKIE_NAME).unsign(
                otp_cookie.value
            )
            user_id = otp_token_generator.get_user_id(otp_token)
            assert user_id == created_user.pk
