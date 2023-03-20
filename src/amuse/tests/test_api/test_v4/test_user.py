import datetime
from decimal import Decimal
from unittest import mock
from urllib.parse import urlparse

import responses
from django.conf import settings
from django.core import mail
from django.test import override_settings
from django.urls import reverse_lazy as reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token

from amuse.storages import S3Storage
from releases.models import RoyaltySplit
from releases.tests.factories import SongFactory, RoyaltySplitFactory
from subscriptions.tests.factories import SubscriptionFactory
from users.models import User, UserMetadata
from users.models.royalty_invitation import RoyaltyInvitation
from users.models.song_artist_invitation import SongArtistInvitation
from users.tests.factories import (
    UserFactory,
    Artistv2Factory,
    RoyaltyInvitationFactory,
    TeamInvitationFactory,
    SongArtistInvitationFactory,
)
from ..base import API_V4_ACCEPT_VALUE, AmuseAPITestCase, API_V5_ACCEPT_VALUE


class UserAPIV4TestCase(AmuseAPITestCase):
    def setUp(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
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
    @mock.patch('amuse.api.v4.serializers.user.fetch_spotify_image', return_value=None)
    def test_create_user(self, mock_fetch):
        bucket = S3Storage(
            bucket_name=settings.AWS_PROFILE_PHOTO_BUCKET_NAME, querystring_auth=False
        )
        url = reverse('user-list')
        user = UserFactory.build(first_name='Foo', last_name='Bar', country='US')
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
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertCountEqual(
            response.data.keys(),
            [
                'id',
                'auth_token',
                'first_name',
                'last_name',
                'artist_name',
                'email',
                'email_verified',
                'category',
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
                'newsletter',
                'spotify_id',
                'spotify_image',
                'is_pro',
                'is_eligible_for_free_trial',
                'created',
                'main_artist_profile',
                'apple_signin_id',
            ],
        )
        # Strip off domain - should be just <bucket-name>/<filename> now.
        # response.data['profile_photo'] = re.sub(
        #    '^//.*?/', '', response.data['profile_photo']
        # )
        expected_data = {
            **data,
            'profile_photo': '{}/{}/{}'.format(
                settings.AWS_S3_ENDPOINT_URL,
                settings.AWS_PROFILE_PHOTO_BUCKET_NAME,
                user.profile_photo,
            ),
            'email_verified': False,
        }
        # Pop off write only fields
        expected_data.pop('password')
        expected_data.pop('facebook_access_token')
        expected_data.pop('google_id_token')
        expected_data.pop('royalty_token')
        expected_data.pop('user_artist_role_token')
        expected_data.pop('impact_click_id')

        for k in expected_data.keys():
            self.assertEqual(expected_data[k], response.data[k], f'"{k}" was not equal')
        user_id = response.data['id']
        self.assertEqual(response.data['first_name'], 'Foo')
        self.assertEqual(response.data['last_name'], 'Bar')
        self.assertEqual(response.data["spotify_id"], user.spotify_id)
        self.assertIsNotNone(Token.objects.filter(user=user_id).first())
        # Make sure the verification link works
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.template_name, 'EMAIL_VERIFICATION')
        self.assertIn(user.email, sent_email.merge_vars)
        verification_url = sent_email.merge_vars[user.email]['URL']
        verification_url = urlparse(verification_url).path
        response = self.client.get(verification_url)
        self.assertRedirects(
            response=response, expected_url=reverse('email_verification_done')
        )
        dbuser = User.objects.get(id=user_id)
        # Ensure that the account is now verified
        self.assertTrue(dbuser.email_verified)
        self.assertEqual(dbuser.spotify_id, user.spotify_id)

        # Check for a created Artist
        self.assertEqual(dbuser.artistv2_set.count(), 1)
        # Check field propagation
        artist = dbuser.artistv2_set.get()
        self.assertEqual(dbuser.artist_name, artist.name)
        self.assertEqual(dbuser.spotify_page, artist.spotify_page)
        self.assertEqual(dbuser.spotify_id, artist.spotify_id)

        meta = UserMetadata.objects.filter(user=dbuser).first()
        self.assertIsNotNone(meta)
        self.assertEqual('impact123', meta.impact_click_id)

        # Users are not pro by default
        assert not dbuser.is_pro
        mock_fetch.assert_called_once()

    @responses.activate
    def test_is_pro_flag(self):
        self.user.email_verified = True
        self.user.save()
        self.client.force_authenticate(user=self.user)
        url = reverse('user-detail', kwargs={'pk': self.user.pk})

        # is_pro is read only
        assert not self.user.is_pro
        data = self.data
        data['is_pro'] = True
        data['firebase_token'] = ''
        data['google_id'] = ''
        data['facebook_id'] = ''
        self.client.patch(url, data)
        self.user.refresh_from_db
        assert not self.user.is_pro

        # is_pro flag available through API
        response = self.client.get(url, format='json').json()
        assert not response['is_pro']

        SubscriptionFactory(user=self.user)
        response = self.client.get(url, format='json').json()
        assert response['is_pro']

    @responses.activate
    def test_create_user_without_artist_name(self):
        bucket = S3Storage(
            bucket_name=settings.AWS_PROFILE_PHOTO_BUCKET_NAME, querystring_auth=False
        )
        url = reverse('user-list')
        user = UserFactory.build(
            first_name='Foo', last_name='Bar', country='US', artist_name=None
        )
        profile_photo = user.profile_photo
        with bucket.open(profile_photo, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())

        user.artist_name = None
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'user_artist_role_token': None,
            **{k: getattr(user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    @responses.activate
    def test_do_not_create_user_without_empty_artist_name(self):
        bucket = S3Storage(
            bucket_name=settings.AWS_PROFILE_PHOTO_BUCKET_NAME, querystring_auth=False
        )
        url = reverse('user-list')
        user = UserFactory.build(
            first_name='Foo', last_name='Bar', country='US', artist_name=None
        )
        # Make sure the profile photo exists
        profile_photo = user.profile_photo
        with bucket.open(profile_photo, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())

        user.artist_name = ''
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'user_artist_role_token': None,
            **{k: getattr(user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @mock.patch('app.util.user_profile_photo_s3_url', autospec=True)
    def test_update(self, mock_s3):
        user = UserFactory(
            email='my.original@example.com', email_verified=True, password='test123'
        )
        user.create_artist_v2('DJ Snow')
        url = reverse('user-detail', args=[user.id])
        password = user.password

        data = {
            'email': 'test123@example.com',
            'password': 'hunter2',
            'first_name': 'Lil',
            'last_name': 'Dork',
            'artist_name': 'Lil King of Snow',
            'spotify_page': 'spotify/lilking',
            'profile_photo': 'avatar.jpg',
        }

        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(user=user)
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()

        self.assertTrue(user.email_verified)
        self.assertEqual(user.email, 'my.original@example.com')
        self.assertEqual(user.password, password)
        self.assertEqual(user.first_name, data['first_name'])
        self.assertEqual(user.last_name, data['last_name'])
        self.assertEqual(response.data['email'], 'my.original@example.com')
        self.assertTrue(response.data['email_verified'])
        self.assertNotIn('password', response.data)
        self.assertEqual(response.data['artist_name'], data['artist_name'])

        data = {
            'email': user.email,
            'profile_photo': 'http://example.com/mallorca-vacay.jpg',
        }
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['profile_photo'], 'http://example.com/mallorca-vacay.jpg'
        )
        user.refresh_from_db()
        self.assertEqual(response.data['profile_photo'], user.profile_photo)

    def test_prevent_changing_phone_number_if_2fa_not_set_up(self):
        user = UserFactory(
            email='my.original@example.com',
            email_verified=True,
            password='test123',
            otp_enabled=False,
            phone_verified=False,
        )
        user.create_artist_v2('DJ Snow')
        url = reverse('user-detail', args=[user.id])
        original_password = user.password
        original_phone = user.phone
        new_phone = '+46700000000'

        assert new_phone != original_phone
        data = {
            'email': 'test123@example.com',
            'password': 'hunter2',
            'first_name': 'Lil',
            'last_name': 'Dork',
            'artist_name': 'Lil King of Snow',
            'spotify_page': 'spotify/lilking',
            'profile_photo': 'avatar.jpg',
            'phone': new_phone,
        }

        self.client.force_authenticate(user=user)
        response = self.client.patch(url, data)
        user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertTrue(user.email_verified)
        self.assertEqual(user.email, 'my.original@example.com')
        self.assertEqual(user.password, original_password)
        self.assertEqual(user.first_name, data['first_name'])
        self.assertEqual(user.last_name, data['last_name'])
        self.assertEqual(response.data['email'], 'my.original@example.com')
        self.assertTrue(response.data['email_verified'])
        self.assertNotIn('password', response.data)
        self.assertEqual(response.data['artist_name'], data['artist_name'])
        self.assertEqual(user.phone, original_phone)  # Phone not changed
        self.assertFalse(user.otp_enabled)
        self.assertFalse(user.phone_verified)

    @override_settings(IP_BLOCK_THROTTLE={'release-create': ['1.1.1.1']})
    def test_blocked_ip(self):
        user = UserFactory()
        artist_v2 = user.create_artist_v2('artist')
        url = reverse('release-list')

        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=user)

        # Make sure we are throttled
        remote_addr = settings.IP_BLOCK_THROTTLE['release-create'][0]
        data = {'artist_id': artist_v2.id}
        response = self.client.post(url, data=data, REMOTE_ADDR=remote_addr)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Make sure we reach the data validation step
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('amuse.api.base.viewsets.user.LoginEndpointThrottle')
    def test_blocked_ip_email_login(self, mock_throttler):
        url = reverse('user-email')
        mock_throttler.return_value = mock.Mock(allow_request=lambda a, b: False)
        data = {'email': self.user.email, 'password': 'seekrit'}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_category_in_response(self):
        user = UserFactory()
        url = reverse('user-detail', args=[user.id])
        self.client.force_authenticate(user=user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('category', response.data)
        self.assertEqual(user.get_category_display().lower(), response.data['category'])

    @responses.activate
    @mock.patch('amuse.api.v4.serializers.user.fetch_spotify_image', return_value=None)
    def test_create_user_with_new_spotify_id_success(self, mock_fetch):
        url = reverse("user-list")

        data = self.data
        data['spotify_id'] = 'NEW_SPOTIFY_ID'
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['spotify_id'], data['spotify_id'])

        created_user = User.objects.get(id=response.data['id'])
        create_user_artist = created_user.artists.first()

        # validate created user and his artist assigned new spotify id
        self.assertEqual(created_user.spotify_id, data['spotify_id'])
        self.assertEqual(create_user_artist.spotify_id, data['spotify_id'])
        mock_fetch.assert_called_once_with(data['spotify_id'], None)

    @responses.activate
    def test_create_user_without_spotify_id_success(self):
        url = reverse("user-list")

        data = self.data
        data.pop('spotify_id')
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue('spotify_id' in response.data)

        created_user = User.objects.get(id=response.data['id'])
        create_user_artist = created_user.artists.first()

        # validate created user and his artist have no spotify id
        self.assertIsNone(created_user.spotify_id)
        self.assertIsNone(create_user_artist.spotify_id)

    @responses.activate
    def test_create_user_with_empty_spotify_id_success(self):
        url = reverse("user-list")

        data = self.data
        del data["spotify_id"]
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue('spotify_id' in response.data)

        created_user = User.objects.get(id=response.data['id'])
        create_user_artist = created_user.artists.first()

        # validate created user and his artist have empty spotify id
        self.assertEqual(created_user.spotify_id, None)
        self.assertEqual(create_user_artist.spotify_id, None)

    @responses.activate
    def test_create_user_with_null_spotify_id_success(self):
        url = reverse("user-list")

        data = self.data
        data['spotify_id'] = None
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue('spotify_id' in response.data)

        created_user = User.objects.get(id=response.data['id'])
        create_user_artist = created_user.artists.first()

        # validate created user and his artist have no spotify id
        self.assertIsNone(created_user.spotify_id)
        self.assertIsNone(create_user_artist.spotify_id)

    @responses.activate
    @mock.patch('amuse.api.v4.serializers.user.fetch_spotify_image', return_value=None)
    def test_create_user_with_existing_not_claimed_spotify_id_success(self, mock_fetch):
        existing_not_claimed_spotify_id = 'EXISTING_NOT_CLAIMED_SPOTIFY_ID'
        existing_artist = Artistv2Factory(
            name='Existing Artist', spotify_id=existing_not_claimed_spotify_id
        )
        existing_artist.userartistrole_set.all().delete()
        existing_artist.owner = None
        existing_artist.save()

        data = self.data
        data['spotify_id'] = existing_not_claimed_spotify_id
        response = self.client.post(reverse('user-list'), data, format='json')

        # validate new user created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        created_user = User.objects.get(id=response.data['id'])
        create_user_artist = created_user.artists.first()

        # validate created user and his artist assigned existing spotify id
        self.assertEqual(created_user.spotify_id, existing_not_claimed_spotify_id)
        self.assertEqual(create_user_artist.spotify_id, existing_not_claimed_spotify_id)
        # validate new artist created for created user
        self.assertNotEqual(existing_artist, create_user_artist, response.data)
        mock_fetch.assert_called_once()

    @responses.activate
    def test_create_user_with_existing_claimed_spotify_id_fails(self):
        existing_claimed_spotify_id = 'EXISTING_CLAIMED_SPOTIFY_ID'
        existing_user = UserFactory()
        existing_user.create_artist_v2(
            name='Claimed Artist', spotify_id=existing_claimed_spotify_id
        )

        data = self.data
        data['spotify_id'] = existing_claimed_spotify_id
        response = self.client.post(reverse('user-list'), data, format='json')

        # validate user creation fails
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_user_with_existing_exact_non_normalized_email(self):
        url = reverse('user-list')
        email = 'Jon@example.com'
        non_normalized_email = 'Jon@Example.COM'

        user = UserFactory(email=email)

        response = self.client.post(
            url,
            {
                "first_name": "Test",
                "last_name": "Test",
                "artist_name": "Test",
                "country": "US",
                "email": non_normalized_email,
                "phone": "+123",
                "language": "en",
                "facebook_id": "",
                "facebook_access_token": "",
                "google_id": "",
                "google_id_token": "",
                "profile_link": "",
                "profile_photo": "",
                "firebase_token": "",
                "password": "",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data, {'email': ['user with this email already exists.']}
        )

    @responses.activate
    @mock.patch('amuse.api.v4.serializers.user.split_accepted')
    @mock.patch('amuse.api.v4.serializers.user.fetch_spotify_image', return_value=None)
    def test_activate_confirmed_royalty_splits(self, mock_fetch, mock_segment):
        inviter = UserFactory(artist_name=None)
        song = SongFactory()
        RoyaltySplitFactory(
            song=song,
            rate=Decimal("0.5"),
            status=RoyaltySplit.STATUS_CONFIRMED,
            revision=1,
        )
        royalty_split_data = {
            'song': song,
            'rate': 0.5,
            'start_date': datetime.date.today(),
            'revision': 1,
        }
        split = RoyaltySplitFactory(**royalty_split_data)

        token = "123"
        invitation = RoyaltyInvitationFactory(
            inviter=inviter,
            token=token,
            status=RoyaltyInvitation.STATUS_PENDING,
            royalty_split=split,
            last_sent=timezone.now(),
        )

        url = reverse('user-list')

        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': token,
            'user_artist_role_token': None,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, RoyaltyInvitation.STATUS_ACCEPTED)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        splits = RoyaltySplit.objects.filter(
            revision=1, status=RoyaltySplit.STATUS_ACTIVE
        )

        self.assertEqual(splits.count(), 2)
        self.assertEqual(splits[0].rate + splits[1].rate, Decimal("1.0"))
        mock_segment.assert_called_once_with(invitation.royalty_split)

    @responses.activate
    @mock.patch('amuse.api.v4.serializers.user.fetch_spotify_image', return_value=None)
    def test_does_not_activate_other_status_royalty_splits(self, mock_fetch):
        inviter = UserFactory(artist_name=None)
        song = SongFactory()
        pending_split = RoyaltySplitFactory(
            song=song,
            rate=Decimal("0.5"),
            status=RoyaltySplit.STATUS_PENDING,
            revision=1,
        )
        royalty_split_data = {
            'song': song,
            'rate': 0.5,
            'start_date': datetime.date.today(),
            'revision': 1,
        }
        split = RoyaltySplitFactory(**royalty_split_data)

        token = "123"
        invitation = RoyaltyInvitationFactory(
            inviter=inviter,
            token=token,
            status=RoyaltyInvitation.STATUS_PENDING,
            royalty_split=split,
            last_sent=timezone.now(),
        )

        url = reverse('user-list')

        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': token,
            'user_artist_role_token': None,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        invitation.refresh_from_db()
        pending_split.refresh_from_db()
        split.refresh_from_db()

        self.assertEqual(pending_split.status, RoyaltySplit.STATUS_PENDING)
        self.assertEqual(split.status, RoyaltySplit.STATUS_CONFIRMED)
        self.assertEqual(invitation.status, RoyaltyInvitation.STATUS_ACCEPTED)
        self.assertEqual(pending_split.rate + split.rate, Decimal("1.0"))

    @responses.activate
    def test_create_user_with_invite_royalty_token(self):
        inviter = UserFactory(artist_name=None)
        song = SongFactory()
        royalty_split_data = {
            'song': song,
            'rate': 1.0,
            'start_date': datetime.date.today(),
        }
        split = RoyaltySplitFactory(**royalty_split_data)

        token = "123"
        RoyaltyInvitationFactory(
            inviter=inviter,
            token=token,
            status=RoyaltyInvitation.STATUS_PENDING,
            royalty_split=split,
            last_sent=timezone.now(),
        )

        url = reverse('user-list')

        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': token,
            'user_artist_role_token': None,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertCountEqual(
            response.data.keys(),
            [
                'id',
                'auth_token',
                'first_name',
                'last_name',
                'artist_name',
                'email',
                'email_verified',
                'category',
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
                'newsletter',
                'spotify_id',
                'spotify_image',
                'is_pro',
                'is_eligible_for_free_trial',
                'created',
                'main_artist_profile',
                'apple_signin_id',
            ],
            msg="different count of data keys",
        )

        expected_data = {
            **data,
            'profile_photo': '{}/{}/{}'.format(
                settings.AWS_S3_ENDPOINT_URL,
                settings.AWS_PROFILE_PHOTO_BUCKET_NAME,
                self.user.profile_photo,
            ),
            'email_verified': False,
        }
        # Pop off write only fields
        expected_data.pop('password')
        expected_data.pop('facebook_access_token')
        expected_data.pop('google_id_token')
        expected_data.pop('royalty_token')
        expected_data.pop('user_artist_role_token')

        for k in expected_data.keys():
            self.assertEqual(expected_data[k], response.data[k], f'"{k}" was not equal')
        user_id = response.data['id']
        self.assertEqual(
            response.data['first_name'], 'Foo', msg="first_name is not equal"
        )
        self.assertEqual(
            response.data['last_name'], 'Bar', msg="last_name is not equal"
        )
        self.assertEqual(
            response.data["spotify_id"], self.user.spotify_id, msg="spotify_id mismatch"
        )
        self.assertIsNotNone(
            Token.objects.filter(user=user_id).first(), msg="token is not none"
        )
        dbuser = User.objects.get(id=user_id)

        # Check for a created Artist
        self.assertEqual(
            dbuser.artistv2_set.count(), 0, msg="count_of_created artists mismatch"
        )

        # Users are not pro by default
        assert not dbuser.is_pro

    @responses.activate
    @mock.patch('amuse.api.v4.serializers.user.logger.warning')
    def test_create_user_with_nonexisting_invite_royalty_token(self, mock_logger):
        token = "token.jwt.random"
        url = reverse('user-list')
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': token,
            'user_artist_role_token': None,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )
        mock_logger.assert_called_once_with(
            f'Royalty invite token: "{token}" does not exist'
        )

    @responses.activate
    def test_create_user_with_invalid_invite_royalty_token(self):
        token = "token.jwt.random"
        inviter = UserFactory(artist_name="Samuel F Lampard")

        song = SongFactory()
        royalty_split_data = {
            'song': song,
            'rate': 0.5,
            'start_date': datetime.date.today(),
        }
        split = RoyaltySplitFactory(**royalty_split_data)
        invite = RoyaltyInvitationFactory(
            inviter=inviter,
            token=token,
            status=RoyaltyInvitation.STATUS_DECLINED,
            royalty_split=split,
            last_sent=timezone.now(),
        )

        self.assertFalse(invite.valid)

        url = reverse('user-list')
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': token,
            'user_artist_role_token': None,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @responses.activate
    def test_create_user_with_invite_royalty_token_invitee_not_none(self):
        token = "token.jwt.random"
        inviter = UserFactory(artist_name="Samuel F Lampard")

        song = SongFactory()
        royalty_split_data = {
            'song': song,
            'rate': 0.5,
            'start_date': datetime.date.today(),
        }
        split = RoyaltySplitFactory(**royalty_split_data)
        RoyaltyInvitationFactory(
            inviter=inviter,
            invitee=UserFactory(artist_name="Ka"),
            token=token,
            status=RoyaltyInvitation.STATUS_PENDING,
            royalty_split=split,
            last_sent=timezone.now(),
        )

        url = reverse('user-list')
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': token,
            'user_artist_role_token': None,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        with self.assertRaises(AssertionError) as context:
            response = self.client.post(url, data, format='json')
        assert isinstance(context.exception, AssertionError)
        self.assertEqual(
            'invitation is created for existing user', str(context.exception)
        )

    def test_create_user_with_songroletoken_and_userartistroletoken(self):
        url = reverse('user-list')
        email = 'test@example.com'

        UserFactory(artist_name="Samuel F Lampard")
        response = self.client.post(
            url,
            {
                "first_name": "Test",
                "last_name": "Test",
                "artist_name": "Test",
                "country": "US",
                "email": email,
                "phone": "+123",
                "language": "en",
                "facebook_id": "",
                "facebook_access_token": "",
                "google_id": "",
                "google_id_token": "",
                "profile_link": "",
                "profile_photo": "",
                "firebase_token": "",
                "password": "",
                "royalty_token": "123",
                "user_artist_role_token": "123",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                'non_field_errors': [
                    'only one of the following fields can be set at the same time: ['
                    'royalty_token, user_artist_role_token, song_artist_token]'
                ]
            },
        )

    @responses.activate
    def test_create_user_with_invite_user_artist_role_token(self):
        token = "token.jwt.random"

        inviter = UserFactory(artist_name="Samuel F Lampard")
        TeamInvitationFactory(inviter=inviter, invitee=None, token=token)

        url = reverse('user-list')

        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'user_artist_role_token': token,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertCountEqual(
            response.data.keys(),
            [
                'id',
                'auth_token',
                'first_name',
                'last_name',
                'artist_name',
                'email',
                'email_verified',
                'category',
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
                'newsletter',
                'spotify_id',
                'spotify_image',
                'is_pro',
                'is_eligible_for_free_trial',
                'created',
                'main_artist_profile',
                'apple_signin_id',
            ],
            msg="different count of data keys",
        )

        expected_data = {
            **data,
            'profile_photo': '{}/{}/{}'.format(
                settings.AWS_S3_ENDPOINT_URL,
                settings.AWS_PROFILE_PHOTO_BUCKET_NAME,
                self.user.profile_photo,
            ),
            'email_verified': False,
        }
        # Pop off write only fields
        expected_data.pop('password')
        expected_data.pop('facebook_access_token')
        expected_data.pop('google_id_token')
        expected_data.pop('royalty_token')
        expected_data.pop('user_artist_role_token')

        for k in expected_data.keys():
            self.assertEqual(expected_data[k], response.data[k], f'"{k}" was not equal')
        user_id = response.data['id']
        self.assertEqual(
            response.data['first_name'], 'Foo', msg="first_name is not equal"
        )
        self.assertEqual(
            response.data['last_name'], 'Bar', msg="last_name is not equal"
        )
        self.assertEqual(
            response.data["spotify_id"], self.user.spotify_id, msg="spotify_id mismatch"
        )
        self.assertIsNotNone(
            Token.objects.filter(user=user_id).first(), msg="token is not none"
        )
        dbuser = User.objects.get(id=user_id)

        # Users are not pro by default
        assert not dbuser.is_pro

    @responses.activate
    def test_team_invitation_invitee_mismatch(self):
        token = "token.jwt.random"
        inviter = UserFactory(artist_name="Samuel F Lampard")
        invitee = UserFactory(artist_name="Frank F Lampard")
        TeamInvitationFactory(inviter=inviter, invitee=invitee, token=token)
        url = reverse('user-list')
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'user_artist_role_token': token,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @responses.activate
    def test_create_user_with_nonexisting_invite_user_artist_role_token(self):
        token = "token.jwt.random"
        url = reverse('user-list')
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'user_artist_role_token': token,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @responses.activate
    def test_create_user_with_invalid_user_artist_role_token(self):
        token = "token.jwt.random"
        inviter = UserFactory(artist_name="Samuel F Lampard")
        TeamInvitationFactory(
            inviter=inviter, token=token, status=RoyaltyInvitation.STATUS_ACCEPTED
        )
        url = reverse('user-list')
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'user_artist_role_token': token,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )


class SongArtistRoleFlowAPIV4TestCase(AmuseAPITestCase):
    def setUp(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
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
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'user_artist_role_token': None,
            **{k: getattr(user, k) for k in self.keys},
        }
        self.user = user

    @responses.activate
    def test_create_user_song_artist_invite_flow(self):
        from releases.tests.factories import SongFactory

        song = SongFactory()
        token = "token.jwt.random"
        inviter = UserFactory(artist_name="Samuel F Lampard")
        artist = Artistv2Factory(name='I am invited')
        SongArtistInvitationFactory(
            inviter=inviter,
            artist=artist,
            song=song,
            token=token,
            status=SongArtistInvitation.STATUS_PENDING,
        )
        url = reverse('user-list')
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'song_artist_token': token,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    @responses.activate
    def test_create_user_with_invalid_song_artist_invite_flow(self):
        token = "token.jwt.random"
        song = SongFactory()
        inviter = UserFactory(artist_name="Samuel F Lampard")
        artist = Artistv2Factory(name='I am invited')
        SongArtistInvitationFactory(
            inviter=inviter,
            artist=artist,
            song=song,
            token=token,
            status=SongArtistInvitation.STATUS_ACCEPTED,
        )
        url = reverse('user-list')
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'song_artist_token': token,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    @responses.activate
    def test_create_user_with_nonexisting_song_artist_invite_flow(self):
        token = "token.jwt.random"
        url = reverse('user-list')
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'song_artist_token': token,
            **{k: getattr(self.user, k) for k in self.keys},
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )


class UserAPIV4EmptyPasswordTestCase(AmuseAPITestCase):
    def setUp(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
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
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': None,
            'user_artist_role_token': None,
            **{k: getattr(user, k) for k in self.keys},
        }

        self.user = user
        self.facebook_graph_url = 'https://graph.facebook.com/v8.0/me'
        self.fb_login_url = reverse('user-facebook')
        self.fb_params = {'facebook_id': '1337', 'facebook_access_token': 'hunter2'}

    @responses.activate
    @mock.patch('amuse.api.v4.serializers.user.fetch_spotify_image', return_value=None)
    def test_set_unusable_password_on_empty_password(self, mock_fetch):
        bucket = S3Storage(
            bucket_name=settings.AWS_PROFILE_PHOTO_BUCKET_NAME, querystring_auth=False
        )
        url = reverse('user-list')

        user = UserFactory.build(
            first_name='Foo', last_name='Bar', country='US', password=None
        )
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

        data['facebook_id'] = 1337

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        new_user_id = response.data['id']
        new_user = User.objects.get(id=new_user_id)
        assert new_user.has_usable_password() == False

        # Test new user login with facebook
        with responses.RequestsMock() as mocked_request:
            mocked_request.add(
                responses.GET,
                f'{self.facebook_graph_url}?access_token=hunter2&fields=first_name,last_name',
                status=200,
                json={'id': '1337', 'first_name': 'Jon', 'last_name': 'Snow'},
                match_querystring=True,
            )

            self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
            response = self.client.get(self.fb_login_url, self.fb_params)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 1)
            self.assertEqual(response.data[0]['id'], new_user_id)
