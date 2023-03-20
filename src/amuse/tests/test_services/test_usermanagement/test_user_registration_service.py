from unittest import mock

import responses
from django.test import TestCase
from django.urls import reverse_lazy as reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIRequestFactory

from amuse.services.usermanagement import RegistrationService
from amuse.services.usermanagement.signup_flows import (
    RegularFlow,
    RoyaltyInvitationFlow,
    TeamInvitationFlow,
    SongInvitationFlow,
)
from countries.tests.factories import CountryFactory
from users.models import User, UserMetadata, AppsflyerDevice
from users.tests.factories import UserFactory


class TestUserRegistrationservice(TestCase):
    def setUp(self):
        self.user = UserFactory.build()
        self.url = reverse('user-list')
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
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_create_user(self, _, __):
        data = {
            'impact_click_id': 'impact123',
            'appsflyer_id': 'appsflyerid123',
            'idfv': 'idfv',
            'idfa': 'idfa',
            'aaid': 'aaid',
            'oaid': 'oaid',
            'imei': 'imei',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }
        country = CountryFactory(code='US')
        request = APIRequestFactory().post(
            '/users', content_type='application/json', HTTP_CF_IPCOUNTRY='XX'
        )
        user = RegistrationService().create_user(request, data)

        self.assertIsNotNone(user)
        self.assertIsInstance(user, User)

        self.assertIsNotNone(Token.objects.filter(user=user.id).first())

        self.assertEqual(user.artistv2_set.count(), 1, 'Should create an artist')
        artist = user.artistv2_set.get()
        self.assertEqual(user.artist_name, artist.name)
        self.assertEqual(user.spotify_page, artist.spotify_page)
        self.assertEqual(user.spotify_id, artist.spotify_id)
        self.assertTrue(user.otp_enabled)

        meta = UserMetadata.objects.filter(user=user).first()
        self.assertIsNotNone(meta, 'Should create Metadata')
        self.assertEqual('impact123', meta.impact_click_id)
        self.assertFalse(user.is_pro)

        appsflyer_device = AppsflyerDevice.objects.filter(user=user).first()
        self.assertIsNotNone(appsflyer_device)
        self.assertEqual('appsflyerid123', appsflyer_device.appsflyer_id)
        self.assertEqual('idfv', appsflyer_device.idfv)
        self.assertEqual('idfa', appsflyer_device.idfa)
        self.assertEqual('aaid', appsflyer_device.aaid)
        self.assertEqual('oaid', appsflyer_device.oaid)
        self.assertEqual('imei', appsflyer_device.imei)

    @responses.activate
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def test_create_user_without_artist(self, _, __):
        data = {**{k: getattr(self.user, k) for k in self.required_fields}}

        data.pop('artist_name')
        request = APIRequestFactory().post('/users')
        user = RegistrationService().create_user(request, data)

        self.assertIsNotNone(user)
        self.assertIsInstance(user, User)
        self.assertIsNotNone(Token.objects.filter(user=user.id).first())

        self.assertEqual(user.artistv2_set.count(), 0, 'Should create an artist')

    @responses.activate
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(RegularFlow, 'pre_registration')
    @mock.patch.object(RegularFlow, 'post_registration')
    def test_trigger_regular_signup_flow(self, mock_pre, mock_post, _, __):
        data = {**{k: getattr(self.user, k) for k in self.required_fields}}

        request = APIRequestFactory().post('/users')
        RegistrationService().create_user(request, data)

        mock_pre.assert_called_once()
        mock_post.assert_called_once()

    @responses.activate
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(RoyaltyInvitationFlow, 'pre_registration')
    @mock.patch.object(RoyaltyInvitationFlow, 'post_registration')
    def test_trigger_royalty_invite_signup_flow(self, mock_pre, mock_post, _, __):
        data = {
            'royalty_token': '123',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }

        request = APIRequestFactory().post('/post')
        RegistrationService().create_user(request, data)

        mock_pre.assert_called_once()
        mock_post.assert_called_once()

    @responses.activate
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(TeamInvitationFlow, 'pre_registration')
    @mock.patch.object(TeamInvitationFlow, 'post_registration')
    def test_trigger_team_invitation_signup_flow(self, mock_pre, mock_post, _, __):
        data = {
            'user_artist_role_token': '123',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }

        request = APIRequestFactory().post('/users')
        RegistrationService().create_user(request, data)

        mock_pre.assert_called_once()
        mock_post.assert_called_once()

    @responses.activate
    @mock.patch(
        'amuse.services.usermanagement.user_registration_service.fetch_spotify_image',
        return_value=None,
    )
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    @mock.patch.object(SongInvitationFlow, 'pre_registration')
    @mock.patch.object(SongInvitationFlow, 'post_registration')
    def test_trigger_song_invitation_signup_flow(self, mock_pre, mock_post, _, __):
        data = {
            'song_artist_token': '123',
            **{k: getattr(self.user, k) for k in self.required_fields},
        }

        request = APIRequestFactory().post('/users')
        RegistrationService().create_user(request, data)

        mock_pre.assert_called_once()
        mock_post.assert_called_once()
