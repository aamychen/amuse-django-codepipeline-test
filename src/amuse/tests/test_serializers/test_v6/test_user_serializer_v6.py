from unittest import mock

import responses
from django.test import TestCase, override_settings
from django.urls import reverse_lazy as reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from waffle.testutils import override_switch

from amuse.api.v6.serializers.user import UserSerializer
from amuse.services.usermanagement.signup_flows import (
    RoyaltyInvitationFlow,
    TeamInvitationFlow,
    SongInvitationFlow,
)
from amuse.settings.constants import MIN_PASSWORD_LENGTH
from amuse.tests.test_api.base import AmuseAPITestCase, API_V6_ACCEPT_VALUE
from payouts.tests.factories import PayeeFactory
from users.models import User, UserMetadata
from users.tests.factories import UserFactory, UserMetadataFactory


@override_switch('auth:v6:enabled', active=True)
class TestUserSerializer(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.serializer = UserSerializer()

    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_serialized_data(self, _):
        self.user = UserFactory(
            facebook_id='fid',
            firebase_token='ft',
            google_id='gid',
            profile_link='pl',
            profile_photo='pp',
            first_name='foo',
            last_name='bar',
            artist_name='foobar',
            email='foo@bar.com',
            country='SE',
            language='SE',
            apple_signin_id='a123',
            newsletter=True,
        )

        UserMetadataFactory(
            user=self.user, is_fraud_attempted=False, hyperwallet_user_token='xxxx'
        )
        serialized_user = self.serializer.to_representation(instance=self.user)
        self.assertNotIn('facebook_access_token', serialized_user)
        self.assertEqual(serialized_user['facebook_id'], 'fid')
        self.assertEqual(serialized_user['firebase_token'], 'ft')
        self.assertEqual(serialized_user['google_id'], 'gid')
        self.assertNotIn('google_id_token', serialized_user)
        self.assertEqual(serialized_user['profile_link'], 'pl')
        self.assertEqual(serialized_user['profile_photo'], 'pp')
        self.assertFalse(serialized_user['otp_enabled'])
        self.assertFalse(serialized_user['phone_verified'])
        self.assertEqual(serialized_user['tier'], 0, 'Should be FREE tier by default')
        self.assertFalse(
            serialized_user['is_free_trial_active'],
            'New user should not have free-trial option',
        )
        self.assertTrue(serialized_user['is_free_trial_eligible'])
        self.assertFalse(serialized_user['is_frozen'])
        self.assertFalse(serialized_user['is_fraud_attempted'])
        self.assertNotIn('impact_click_id', serialized_user)
        self.assertIsNotNone(serialized_user['auth_token'])
        self.assertEqual(serialized_user['first_name'], 'foo')
        self.assertEqual(serialized_user['last_name'], 'bar')
        self.assertEqual(serialized_user['artist_name'], 'foobar')
        self.assertEqual(serialized_user['email'], 'foo@bar.com')
        self.assertTrue(serialized_user['email_verified'])
        self.assertEqual(serialized_user['category'], 'default')
        self.assertEqual(serialized_user['country'], 'SE')
        self.assertEqual(serialized_user['language'], 'SE')
        self.assertEqual(serialized_user['apple_signin_id'], 'a123')
        self.assertIsNotNone(serialized_user['spotify_id'])

    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_is_frozen(self, _):
        self.user = UserFactory(is_frozen=True)

        UserMetadataFactory(user=self.user, is_fraud_attempted=True)
        serialized_user = self.serializer.to_representation(instance=self.user)
        self.assertTrue(serialized_user['is_frozen'])
        self.assertTrue(serialized_user['is_fraud_attempted'])


class TestUserSerializerSpecificBehaviour(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory()
        self.serializer = UserSerializer()

    def test_payee_profile_exist(self):
        serialized_user = self.serializer.to_representation(self.user)
        self.assertFalse(serialized_user['payee_profile_exist'])
        # Create Payee and repeat test
        PayeeFactory(user=self.user)
        serialized_user = self.serializer.to_representation(self.user)
        self.assertTrue(serialized_user['payee_profile_exist'])


@override_switch('auth:v6:enabled', active=True)
class TestUserSerializerCreate(AmuseAPITestCase):
    def setUp(self):
        self.client.credentials(HTTP_ACCEPT=API_V6_ACCEPT_VALUE)
        self.user = UserFactory.build()
        self.user.password = 'x' * MIN_PASSWORD_LENGTH
        self.url = reverse('user-list')
        self.required_fields = [
            'first_name',
            'last_name',
            'email',
            'country',
            'language',
            'password',
            'artist_name',
            'phone',
        ]

    @responses.activate
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch('amuse.api.v6.serializers.user.validate_phone', return_value=True)
    def test_create_user(self, _, __, ___):
        data = {
            'impact_click_id': 'impact123',
            'appsflyer_id': 'appsflyerid123',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }

        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        user_id = response.data['id']
        self.assertIsNotNone(Token.objects.filter(user=user_id).first())

        dbuser = User.objects.get(id=user_id)
        self.assertEqual(dbuser.artistv2_set.count(), 1, 'Should create an artist')
        artist = dbuser.artistv2_set.get()
        self.assertEqual(dbuser.artist_name, artist.name)
        self.assertEqual(dbuser.spotify_page, artist.spotify_page)
        self.assertEqual(dbuser.spotify_id, artist.spotify_id)

        meta = UserMetadata.objects.filter(user=dbuser).first()
        self.assertIsNotNone(meta, 'Should create Metadata')
        self.assertEqual('impact123', meta.impact_click_id)

    @responses.activate
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch('amuse.api.v6.serializers.user.validate_phone', return_value=True)
    def test_create_user_without_artist(self, _, __, ___):
        data = {
            'impact_click_id': 'impact123',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }

        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        user_id = response.data['id']
        self.assertIsNotNone(Token.objects.filter(user=user_id).first())

        dbuser = User.objects.get(id=user_id)
        self.assertEqual(dbuser.artistv2_set.count(), 1, 'Should create an artist')
        artist = dbuser.artistv2_set.get()
        self.assertEqual(dbuser.artist_name, artist.name)
        self.assertEqual(dbuser.spotify_page, artist.spotify_page)
        self.assertEqual(dbuser.spotify_id, artist.spotify_id)

        meta = UserMetadata.objects.filter(user=dbuser).first()
        self.assertIsNotNone(meta, 'Should create Metadata')
        self.assertEqual('impact123', meta.impact_click_id)

    @responses.activate
    @mock.patch('amuse.api.v6.serializers.user.validate_phone', return_value=True)
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(RoyaltyInvitationFlow, 'pre_registration')
    @mock.patch.object(RoyaltyInvitationFlow, 'post_registration')
    def test_trigger_royalty_invite_signup_flow(self, mock_pre, mock_post, _, __, ___):
        data = {
            'royalty_token': '123',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }

        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        mock_pre.assert_called_once()
        mock_post.assert_called_once()

    @responses.activate
    @mock.patch('amuse.api.v6.serializers.user.validate_phone', return_value=True)
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(TeamInvitationFlow, 'pre_registration')
    @mock.patch.object(TeamInvitationFlow, 'post_registration')
    def test_trigger_team_invitation_signup_flow(self, mock_pre, mock_post, _, __, ___):
        data = {
            'user_artist_role_token': '123',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }

        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        mock_pre.assert_called_once()
        mock_post.assert_called_once()

    @responses.activate
    @mock.patch('amuse.api.v6.serializers.user.validate_phone', return_value=True)
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(SongInvitationFlow, 'pre_registration')
    @mock.patch.object(SongInvitationFlow, 'post_registration')
    def test_trigger_song_invitation_signup_flow(self, mock_pre, mock_post, _, __, ___):
        data = {
            'song_artist_token': '123',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }

        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        mock_pre.assert_called_once()
        mock_post.assert_called_once()

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_raise_error_for_multiple_invitation_tokens(self, _):
        data = {
            'song_artist_token': '123',
            'royalty_token': 'rt',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }

        response = self.client.post(self.url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch('amuse.api.v6.serializers.user.validate_phone')
    def test_raise_error_if_invalid_phone(self, mock_validate_phone, _):
        mock_validate_phone.side_effect = ValidationError()
        data = {
            'phone': '123',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }

        response = self.client.post(self.url, data, format='json')
        mock_validate_phone.assert_called_once()
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @responses.activate
    @override_settings(GOOGLE_CAPTCHA_ENABLED=True)
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_raise_error_if_invalid_google_captcha(self, _):
        data = {**{k: getattr(self.user, k) for k in self.required_fields}}

        response = self.client.post(self.url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch('amuse.api.v6.serializers.user.validate_phone', return_value='+123')
    def test_raise_error_if_password_too_short(self, _, __):
        data = {
            **{k: getattr(self.user, k) for k in self.required_fields},
            'password': 'x' * (MIN_PASSWORD_LENGTH - 1),
        }

        response = self.client.post(self.url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch('amuse.api.v6.serializers.user.validate_phone', return_value='+123')
    def test_raise_error_if_password_is_null(self, _, __):
        data = {
            **{k: getattr(self.user, k) for k in self.required_fields},
            'password': None,
        }

        response = self.client.post(self.url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch('amuse.api.v6.serializers.user.validate_phone', return_value='+123')
    def test_ignore_password_if_social_login_exists_in_request(self, _, __):
        social_login_ids = [
            'google_id_token',
            'apple_signin_id',
            'facebook_access_token',
        ]

        for social_login_id in social_login_ids:
            with self.subTest():
                user = UserFactory.build()
                data = {
                    **{k: getattr(user, k) for k in self.required_fields},
                    social_login_id: '123',
                    'password': None,
                }

                response = self.client.post(self.url, data, format='json')
                self.assertEqual(
                    response.status_code, status.HTTP_201_CREATED, response.data
                )


@override_switch('auth:v6:enabled', active=True)
class TestUserSerializerUpdate(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()

        self.client.credentials(HTTP_ACCEPT=API_V6_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)
        self.url = reverse('user-detail', args=[self.user.pk])
        self.required_fields = [
            'first_name',
            'last_name',
            'email',
            'country',
            'language',
            'password',
            'artist_name',
        ]

    @responses.activate
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_update_user(self, _):
        data = {
            'impact_click_id': 'impact123',
            'appsflyer_id': 'appsflyerid123',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
