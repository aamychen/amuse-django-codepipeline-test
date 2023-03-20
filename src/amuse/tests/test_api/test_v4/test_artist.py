from django.urls import reverse_lazy as reverse
import responses
from rest_framework import status
from unittest.mock import patch
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from releases.tests.factories import SongFactory, SongArtistRoleFactory, ReleaseFactory
from users.models import ArtistV2, UserArtistRole, TeamInvitation, User
from releases.models.release import ReleaseArtistRole, Release
from releases.models.song import SongArtistRole
from users.tests.factories import (
    UserFactory,
    Artistv2Factory,
    UserArtistRoleFactory,
    TeamInvitationFactory,
)


class ArtistV2APITestCase(AmuseAPITestCase):
    def setUp(self):
        super().setUp()

        self.user = UserFactory(is_pro=True)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user)
        self.request_payload = {
            "name": "Test Artist v2",
            "spotify_page": "https://spotify.com/artists/123",
            "twitter_name": "artistv2",
            "facebook_page": "https://www.facebook.com/pages/artistv2",
            "instagram_name": "https://instagram.com/users/artistv2",
            "soundcloud_page": "https://soundcloud.com/users/artistv2",
            "youtube_channel": "https://www.youtube.com/users/artistv2",
            "spotify_id": "7dGJo4pcD2V6oG8kP0tJRR",
            "apple_id": "artistv2@example.com",
        }

    @responses.activate
    @patch('amuse.api.v4.serializers.artist.fetch_spotify_image', return_value=None)
    def test_create_artist_success(self, mock_fetch):
        url = reverse('artist-list')

        expected_response_keys = [
            'id',
            'name',
            'created',
            'spotify_page',
            'twitter_name',
            'facebook_page',
            'instagram_name',
            'tiktok_name',
            'soundcloud_page',
            'youtube_channel',
            'spotify_id',
            'spotify_image',
            'apple_id',
            'has_owner',
            'role',
            'releases_count',
            'owner',
            'main_artist_profile',
            'has_spotify_for_artists',
            'has_audiomack',
            'audiomack_profile_url',
            'spotify_profile_url',
        ]

        payload = self.request_payload
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(list(response.data.keys()), expected_response_keys)

        self.assertIsNotNone(response.data['id'])
        self.assertEqual(payload['name'], response.data['name'])
        self.assertEqual(payload['spotify_page'], response.data['spotify_page'])
        self.assertEqual(payload['twitter_name'], response.data['twitter_name'])
        self.assertEqual(payload['facebook_page'], response.data['facebook_page'])
        self.assertEqual(payload['instagram_name'], response.data['instagram_name'])
        self.assertEqual(payload['soundcloud_page'], response.data['soundcloud_page'])
        self.assertEqual(payload['youtube_channel'], response.data['youtube_channel'])
        self.assertEqual(payload['spotify_id'], response.data['spotify_id'])
        self.assertEqual(payload['apple_id'], response.data['apple_id'])
        self.assertTrue(response.data['has_owner'])
        self.assertEqual(
            dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.OWNER],
            response.data['role'],
        )
        self.assertEqual(0, response.data['releases_count'])
        self.assertIsNotNone(response.data['owner'])
        self.assertEqual(response.data['owner']['id'], self.user.id)
        self.assertEqual(response.data['owner']['first_name'], self.user.first_name)
        self.assertEqual(response.data['owner']['last_name'], self.user.last_name)
        self.assertEqual(
            response.data['owner']['profile_photo'], self.user.profile_photo
        )
        self.assertFalse(response.data['has_spotify_for_artists'])
        self.assertFalse(response.data['has_audiomack'])
        self.assertIsNone(response.data['audiomack_profile_url'])
        self.assertEqual(
            response.data['spotify_profile_url'],
            'https://open.spotify.com/artist/{}'.format(payload['spotify_id']),
        )
        mock_fetch.assert_called_once()

    @responses.activate
    @patch('amuse.api.v4.serializers.artist.fetch_spotify_image', return_value=None)
    def test_updating_artist_name_disabled(self, mock_fetch):
        url = reverse('artist-list')

        response = self.client.post(url, self.request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        artist_id = response.data['id']

        update_payload = {'name': 'New Artist Name V2'}
        update_url = reverse('artist-detail', args=[artist_id])
        response = self.client.put(update_url, update_payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

        artist = ArtistV2.objects.get(id=artist_id)
        self.assertNotEqual(artist.name, update_payload['name'])
        mock_fetch.assert_called_once()

    @responses.activate
    @patch('amuse.api.v4.serializers.artist.fetch_spotify_image', return_value=None)
    def test_create_artist_for_non_pro_user_without_artist_success(self, mock_fetch):
        # make our user free user with no artist
        self.user.subscriptions.all().delete()
        self.user.save()
        UserArtistRole.objects.filter(user=self.user).delete()

        # create artist for user
        url = reverse('artist-list')
        payload = self.request_payload
        response = self.client.post(url, payload, format='json')

        # validate artist successfully created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_fetch.assert_called_once()

    @responses.activate
    @patch('amuse.api.v4.serializers.artist.fetch_spotify_image', return_value=None)
    def test_create_multiple_artists_for_pro_user_success(self, mock_fetch):
        url = reverse('artist-list')

        for i in range(5):
            # create artist for user
            payload = self.request_payload
            for artist_property in payload:
                payload[artist_property] = f"${payload[artist_property]}-${i}"
            response = self.client.post(url, payload, format='json')
            # validate artist successfully created
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(5, mock_fetch.call_count)

    @responses.activate
    def test_create_artist_for_frozen_user_not_allowed(self):
        self.user.is_frozen = True
        self.user.save()
        self.user.refresh_from_db()

        # create artist for user
        url = reverse('artist-list')
        payload = self.request_payload
        response = self.client.post(url, payload, format='json')

        # validate artist creation was not allowed
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    @responses.activate
    def test_create_artist_for_non_pro_user_with_artist_not_allowed(self):
        # make our user free user with artist
        self.user.subscriptions.all().delete()
        self.user.save()
        self.user.create_artist_v2(name='My artist')

        # create artist for user
        url = reverse('artist-list')
        payload = self.request_payload
        response = self.client.post(url, payload, format='json')

        # validate artist creation was not allowed
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    @patch('amuse.api.v4.serializers.artist.fetch_spotify_image', return_value=None)
    def test_create_artist_with_existing_not_claimed_spotify_success(self, mock_fetch):
        # create existing artist with spotify, but without an owner
        existing_artist = Artistv2Factory(
            name='Artist', spotify_id='existing', owner=None
        )
        # create artist for user
        url = reverse('artist-list')
        payload = self.request_payload
        payload['spotify_id'] = existing_artist.spotify_id
        response = self.client.post(url, payload, format='json')
        # validate artist successfully created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_fetch.assert_called_once()

    @responses.activate
    def test_create_artist_with_existing_claimed_spotify_fails(self):
        # create existing claimed artist with spotify
        artist_owner = UserFactory()
        existing_claimed_artist = artist_owner.create_artist_v2(
            name='Artist', spotify_id='claimed'
        )
        # create artist for user
        url = reverse('artist-list')
        payload = self.request_payload
        payload['spotify_id'] = existing_claimed_artist.spotify_id
        response = self.client.post(url, payload, format='json')
        # validate artist creation fails
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @responses.activate
    def test_spotify_profile_url(self):
        my_artist = Artistv2Factory(name='MyArtist', spotify_id='abcde')
        UserArtistRoleFactory(
            user=self.user, artist=my_artist, type=UserArtistRole.ADMIN
        )
        url = f'/api/artists/{my_artist.pk}/'
        response = self.client.get(url)
        self.assertEqual(
            'https://open.spotify.com/artist/{}'.format(my_artist.spotify_id),
            response.data['spotify_profile_url'],
        )

    @responses.activate
    @patch(
        'amuse.vendor.audiomack.audiomack_api.AudiomackAPI.get_artist_slug',
        return_value='user_slug',
    )
    def test_audiomack_profile_url(self, mock_fetch):
        my_artist = Artistv2Factory(
            name='MyArtist',
            audiomack_id='12345',
            audiomack_access_token="mock",
            audiomack_access_token_secret="mock",
        )
        UserArtistRoleFactory(
            user=self.user, artist=my_artist, type=UserArtistRole.ADMIN
        )
        url = f'/api/artists/{my_artist.pk}/'
        response = self.client.get(url)
        self.assertEqual(
            'https://audiomack.com/user_slug', response.data['audiomack_profile_url']
        )
        mock_fetch.assert_called_once()

    @responses.activate
    @patch(
        'amuse.vendor.audiomack.audiomack_api.AudiomackAPI.get_artist_slug',
        return_value=None,
    )
    def test_audiomack_profile_url_none(self, mock_fetch):
        my_artist = Artistv2Factory(
            name='MyArtist',
            audiomack_id='12345',
            audiomack_access_token="mock",
            audiomack_access_token_secret="mock",
        )
        UserArtistRoleFactory(
            user=self.user, artist=my_artist, type=UserArtistRole.ADMIN
        )
        url = f'/api/artists/{my_artist.pk}/'
        response = self.client.get(url)
        self.assertEqual(None, response.data['audiomack_profile_url'])
        mock_fetch.assert_called_once()

    @responses.activate
    def test_correct_role_retrieved(self):
        my_artist = Artistv2Factory(name='MyArtist')
        UserArtistRoleFactory(
            user=self.user, artist=my_artist, type=UserArtistRole.SPECTATOR
        )

        url = f'/api/artists/{my_artist.pk}/'
        response = self.client.get(url)

        self.assertEqual(my_artist.id, response.data['id'])
        self.assertEqual(
            dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.SPECTATOR],
            response.data['role'],
        )

    @responses.activate
    def test_correct_releases_count_retrieved(self):
        my_artist = self.user.create_artist_v2(name='MyArtist')
        relase_1 = ReleaseFactory()
        ReleaseArtistRole.objects.create(
            release=relase_1,
            artist=my_artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )
        relase_2 = ReleaseFactory()
        ReleaseArtistRole.objects.create(
            release=relase_2,
            artist=my_artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )

        url = f'/api/artists/{my_artist.pk}/'
        response = self.client.get(url)

        self.assertEqual(my_artist.id, response.data['id'])
        self.assertEqual(2, response.data['releases_count'])

    @responses.activate
    def test_releases_count_excludes_rejected_deleted(self):
        my_artist = self.user.create_artist_v2(name='MyArtist')
        relase_1 = ReleaseFactory(status=Release.STATUS_REJECTED)
        ReleaseArtistRole.objects.create(
            release=relase_1,
            artist=my_artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )
        relase_2 = ReleaseFactory(status=Release.STATUS_DELETED)
        ReleaseArtistRole.objects.create(
            release=relase_2,
            artist=my_artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )
        relase_3 = ReleaseFactory()
        ReleaseArtistRole.objects.create(
            release=relase_3,
            artist=my_artist,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
        )

        url = f'/api/artists/{my_artist.pk}/'
        response = self.client.get(url)

        self.assertEqual(my_artist.id, response.data['id'])
        self.assertEqual(1, response.data['releases_count'])

    @responses.activate
    @patch('amuse.api.v4.serializers.artist.fetch_spotify_image', return_value=None)
    def test_artist_associated_to_user(self, mock_fetch):
        url = reverse('artist-list')
        response = self.client.post(url, self.request_payload, format='json')

        artist = ArtistV2.objects.get(id=response.data['id'])

        # test user added as owner for the artist
        self.assertTrue(
            UserArtistRole.objects.filter(
                artist_id=artist.id, user_id=self.user.id, type=UserArtistRole.OWNER
            ).exists()
        )
        mock_fetch.assert_called_once()

    @responses.activate
    def test_related_artists_retrieved(self):
        my_artists_ids = set()
        other_artists_ids = set()
        for role in dict(UserArtistRole.TYPE_CHOICES).keys():
            my_artist = Artistv2Factory(name='MyArtist')
            UserArtistRoleFactory(user=self.user, artist=my_artist, type=role)
            my_artists_ids.add(my_artist.id)
            other_artist = Artistv2Factory(name='OtherArtist')
            UserArtistRoleFactory(user=UserFactory(), artist=other_artist, type=role)
            other_artists_ids.add(other_artist.id)

        url = reverse('artist-list')
        response = self.client.get(url)

        retrieved_artists_ids = set([a['id'] for a in response.data])

        # All of my related artists are retrieved
        self.assertTrue(len(my_artists_ids - retrieved_artists_ids) == 0)
        # Other user artists are not retrieved
        self.assertEqual(other_artists_ids - retrieved_artists_ids, other_artists_ids)

    @responses.activate
    def test_retrieved_artists_sorted_by_user_role(self):
        artist_roles_sort_order = [
            UserArtistRole.OWNER,
            UserArtistRole.ADMIN,
            UserArtistRole.MEMBER,
            UserArtistRole.SPECTATOR,
        ]

        # Create artists in reverse of the sort order
        for role in artist_roles_sort_order[::-1]:
            artist = Artistv2Factory(name='Artist')
            UserArtistRoleFactory(user=self.user, artist=artist, type=role)

        # Retrieve list of artists
        url = reverse('artist-list')
        response = self.client.get(url)

        # Validate list is ordered by user roles
        self.assertEqual(
            response.data[0]['role'],
            dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.OWNER],
        )
        self.assertEqual(
            response.data[1]['role'],
            dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.ADMIN],
        )
        self.assertEqual(
            response.data[2]['role'],
            dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.MEMBER],
        )
        self.assertEqual(
            response.data[3]['role'],
            dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.SPECTATOR],
        )

    @responses.activate
    def test_team_info_for_related_artist_retrieved(self):
        my_artist = self.user.create_artist_v2(name='MyArtist')
        my_artist2 = self.user.create_artist_v2(name='MyArtist2')

        owner_role = UserArtistRole.objects.get(user=self.user, artist=my_artist)
        admin_role = UserArtistRoleFactory(
            artist=my_artist, user=UserFactory(), type=UserArtistRole.ADMIN
        )
        member_invite = TeamInvitationFactory(
            inviter=self.user,
            artist=my_artist,
            team_role=TeamInvitation.TEAM_ROLE_MEMBER,
        )

        TeamInvitationFactory(
            inviter=self.user,
            artist=my_artist,
            team_role=TeamInvitation.TEAM_ROLE_MEMBER,
            status=TeamInvitation.STATUS_EXPIRED,
        )

        # Create one more invite which will be filtered since status not in (pending, expired)
        TeamInvitationFactory(
            inviter=self.user,
            artist=my_artist,
            team_role=TeamInvitation.TEAM_ROLE_MEMBER,
            status=TeamInvitation.STATUS_ACCEPTED,
        )

        url = f'/api/artists/{my_artist.pk}/team/'
        response = self.client.get(url)

        self.assertIsNotNone(response.data['roles'])
        self.assertEqual(2, len(response.data['roles']))
        self.assertTrue(owner_role.id in [r['id'] for r in response.data['roles']])
        self.assertTrue(admin_role.id in [r['id'] for r in response.data['roles']])

        self.assertIsNotNone(response.data['invites'])
        self.assertEqual(2, len(response.data['invites']))
        self.assertTrue(member_invite.id in [i['id'] for i in response.data['invites']])

    @responses.activate
    def test_team_info_for_non_related_artist_cannot_be_retrieved(self):
        other_user = UserFactory()
        other_artist = other_user.create_artist_v2(name='OtherArtist')
        UserArtistRoleFactory(
            artist=other_artist, user=UserFactory(), type=UserArtistRole.ADMIN
        )
        TeamInvitationFactory(
            inviter=self.user,
            artist=other_artist,
            team_role=TeamInvitation.TEAM_ROLE_MEMBER,
        )

        url = f'/api/artists/{other_artist.pk}/team/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @responses.activate
    def test_team_info_roles_sorting_general_case(self):
        now = timezone.now()

        def create_role(user, artist, role, created):
            user_artist_role = UserArtistRoleFactory(
                user=user, artist=artist, type=role
            )
            user_artist_role.created = created
            user_artist_role.save()
            return user_artist_role

        user = UserFactory(is_pro=True)
        my_artist = user.create_artist_v2(name='MyArtist')

        owner_role = UserArtistRole.objects.get(user=user, artist=my_artist)

        admin_role = create_role(
            UserFactory(),
            my_artist,
            UserArtistRole.ADMIN,
            now + relativedelta(months=1),
        )
        spectator_role = create_role(
            self.user,
            my_artist,
            UserArtistRole.SPECTATOR,
            now - relativedelta(months=2),
        )
        member_role = create_role(
            UserFactory(),
            my_artist,
            UserArtistRole.MEMBER,
            now - relativedelta(months=4),
        )

        url = f'/api/artists/{my_artist.pk}/team/'
        response = self.client.get(url)

        self.assertIsNotNone(response.data['roles'])
        roles = response.data['roles']

        # role of signed-in user must be first
        # owner role must be second
        # rest of the roles must be sorted chronologically when added
        # (NOT accepted by recipient and NOT by permissions level)
        self.assertEqual(4, len(roles))
        self.assertEqual(spectator_role.id, roles[0]['id'])
        self.assertEqual(owner_role.id, roles[1]['id'])
        self.assertEqual(member_role.id, roles[2]['id'])
        self.assertEqual(admin_role.id, roles[3]['id'])

    @responses.activate
    def test_team_info_roles_sorting_owner_is_signedin(self):
        now = timezone.now()

        def create_role(user, artist, role, created):
            user_artist_role = UserArtistRoleFactory(
                user=user, artist=artist, type=role
            )
            user_artist_role.created = created
            user_artist_role.save()
            return user_artist_role

        my_artist = self.user.create_artist_v2(name='MyArtist')

        owner_role = UserArtistRole.objects.get(user=self.user, artist=my_artist)
        admin_role = create_role(
            UserFactory(),
            my_artist,
            UserArtistRole.ADMIN,
            now + relativedelta(months=1),
        )
        spectator_role = create_role(
            UserFactory(),
            my_artist,
            UserArtistRole.SPECTATOR,
            now - relativedelta(months=2),
        )
        member_role = create_role(
            UserFactory(),
            my_artist,
            UserArtistRole.MEMBER,
            now - relativedelta(months=4),
        )

        url = f'/api/artists/{my_artist.pk}/team/'
        response = self.client.get(url)

        self.assertIsNotNone(response.data['roles'])
        roles = response.data['roles']

        # role of signed-in user must be first
        # owner role must be second
        # rest of the roles must be sorted chronologically when added
        # (NOT accepted by recipient and NOT by permissions level)
        self.assertEqual(4, len(roles))
        self.assertEqual(owner_role.id, roles[0]['id'])
        self.assertEqual(member_role.id, roles[1]['id'])
        self.assertEqual(spectator_role.id, roles[2]['id'])
        self.assertEqual(admin_role.id, roles[3]['id'])

    @responses.activate
    def test_team_sensitive_data_hidden_for_member(self):
        user = UserFactory()
        artist = user.create_artist_v2(name='UserArtist')
        uar = UserArtistRole.objects.create(
            user=self.user, artist=artist, type=UserArtistRole.MEMBER
        )
        member_invite = TeamInvitationFactory(
            inviter=user, artist=artist, team_role=TeamInvitation.TEAM_ROLE_MEMBER
        )

        url = f'/api/artists/{artist.pk}/team/'
        response = self.client.get(url)

        self.assertIsNotNone(response.data['roles'])
        self.assertEqual(2, len(response.data['roles']))

        self.assertIsNotNone(response.data['invites'])
        self.assertEqual(1, len(response.data['invites']))

        invite = response.data['invites'][0]
        self.assertEqual(invite['email'], '[Filtered]')
        self.assertEqual(invite['phone_number'], '[Filtered]')

    @responses.activate
    def test_team_sensitive_data_hidden_for_spectator(self):
        user = UserFactory()
        artist = user.create_artist_v2(name='UserArtist')
        uar = UserArtistRole.objects.create(
            user=self.user, artist=artist, type=UserArtistRole.SPECTATOR
        )
        member_invite = TeamInvitationFactory(
            inviter=user, artist=artist, team_role=TeamInvitation.TEAM_ROLE_MEMBER
        )

        url = f'/api/artists/{artist.pk}/team/'
        response = self.client.get(url)

        self.assertIsNotNone(response.data['roles'])
        self.assertEqual(2, len(response.data['roles']))

        self.assertIsNotNone(response.data['invites'])
        self.assertEqual(1, len(response.data['invites']))

        invite = response.data['invites'][0]
        self.assertEqual(invite['email'], '[Filtered]')
        self.assertEqual(invite['phone_number'], '[Filtered]')

    @responses.activate
    def test_team_sensitive_data_shown_for_admin(self):
        user = UserFactory()
        artist = user.create_artist_v2(name='UserArtist')
        uar = UserArtistRole.objects.create(
            user=self.user, artist=artist, type=UserArtistRole.ADMIN
        )
        member_invite = TeamInvitationFactory(
            inviter=user, artist=artist, team_role=TeamInvitation.TEAM_ROLE_SPECTATOR
        )

        url = f'/api/artists/{artist.pk}/team/'
        response = self.client.get(url)

        self.assertIsNotNone(response.data['roles'])
        self.assertEqual(2, len(response.data['roles']))

        self.assertIsNotNone(response.data['invites'])
        self.assertEqual(1, len(response.data['invites']))

        invite = response.data['invites'][0]
        self.assertNotEqual(invite['email'], '[Filtered]')
        self.assertNotEqual(invite['phone_number'], '[Filtered]')

    @responses.activate
    def test_team_sensitive_data_shown_for_owner(self):
        user = UserFactory()
        artist = self.user.create_artist_v2(name='UserArtist')
        member_invite = TeamInvitationFactory(
            inviter=self.user,
            invitee=user,
            artist=artist,
            team_role=TeamInvitation.TEAM_ROLE_SPECTATOR,
        )

        url = f'/api/artists/{artist.pk}/team/'
        response = self.client.get(url)

        self.assertIsNotNone(response.data['roles'])
        self.assertEqual(1, len(response.data['roles']))

        self.assertIsNotNone(response.data['invites'])
        self.assertEqual(1, len(response.data['invites']))

        invite = response.data['invites'][0]
        self.assertNotEqual(invite['email'], '[Filtered]')
        self.assertNotEqual(invite['phone_number'], '[Filtered]')

    @responses.activate
    def test_edit_not_allowed_for_user_with_no_edit_permissions(self):
        roles_with_no_edit_permissions = [
            UserArtistRole.MEMBER,
            UserArtistRole.SPECTATOR,
        ]
        for role in roles_with_no_edit_permissions:
            artist = Artistv2Factory(name='Artist')
            UserArtistRoleFactory(user=self.user, artist=artist, type=role)
            url = f'/api/artists/{artist.pk}/'
            response = self.client.put(url, {"name": "UpdateArtist"}, format='json')
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    def test_edit_successful_for_user_with_edit_permissions(self):
        roles_with_edit_permissions = [UserArtistRole.ADMIN, UserArtistRole.OWNER]
        update_request = {
            "name": "Artist",
            "spotify_page": "https://spotify.com/pages/artist-update",
            "twitter_name": "artist-update",
            "facebook_page": "https://www.facebook.com/pages/artist-update",
            "instagram_name": "https://instagram.com/users/artist-update",
            "soundcloud_page": "https://soundcloud.com/users/artist-update",
            "youtube_channel": "https://www.youtube.com/users/artist-update",
            "spotify_id": "",
            "apple_id": "artist-update@example.com",
        }
        for role in roles_with_edit_permissions:
            artist = Artistv2Factory(name='Artist')
            UserArtistRoleFactory(user=self.user, artist=artist, type=role)
            url = f'/api/artists/{artist.pk}/'
            response = self.client.put(url, update_request, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            artist.refresh_from_db()

            self.assertEqual(artist.spotify_page, update_request['spotify_page'])
            self.assertEqual(artist.twitter_name, update_request['twitter_name'])
            self.assertEqual(artist.facebook_page, update_request['facebook_page'])
            self.assertEqual(artist.instagram_name, update_request['instagram_name'])
            self.assertEqual(artist.soundcloud_page, update_request['soundcloud_page'])
            self.assertEqual(artist.youtube_channel, update_request['youtube_channel'])
            self.assertEqual(artist.spotify_id, update_request['spotify_id'])
            self.assertEqual(artist.apple_id, update_request['apple_id'])

    @responses.activate
    def test_social_media_data_edit_not_allowed_for_user_with_no_permissions(self):
        roles_with_no_some_edit_permissions = [UserArtistRole.SPECTATOR]

        for role in roles_with_no_some_edit_permissions:
            artist = Artistv2Factory(name='Artist')
            UserArtistRoleFactory(user=self.user, artist=artist, type=role)
            url = f'/api/artists/{artist.pk}/social_media/'
            response = self.client.post(
                url, {"spotify_page": "https://spotify.com/artists/123"}, format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    def test_social_media_data_edit_successful_for_user_with_permissions(self):
        roles_with_some_edit_permissions = [
            UserArtistRole.OWNER,
            UserArtistRole.ADMIN,
            UserArtistRole.MEMBER,
        ]

        some_update_req = {
            "spotify_page": "https://spotify.com/pages/some-update",
            "spotify_id": "some-update",
            "twitter_name": "some-update",
            "facebook_page": "https://www.facebook.com/pages/some-update",
            "instagram_name": "https://instagram.com/users/some-update",
            "soundcloud_page": "https://soundcloud.com/users/some-update",
            "youtube_channel": "https://www.youtube.com/users/some-update",
        }

        for role in roles_with_some_edit_permissions:
            artist_owner = UserFactory()
            artist = artist_owner.create_artist_v2(name="OtherArtist")
            UserArtistRoleFactory(user=self.user, artist=artist, type=role)
            url = f'/api/artists/{artist.pk}/social_media/'
            response = self.client.post(url, some_update_req, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            artist.refresh_from_db()

            self.assertEqual(artist.spotify_page, some_update_req['spotify_page'])
            self.assertEqual(artist.twitter_name, some_update_req['twitter_name'])
            self.assertEqual(artist.facebook_page, some_update_req['facebook_page'])
            self.assertEqual(artist.instagram_name, some_update_req['instagram_name'])
            self.assertEqual(artist.soundcloud_page, some_update_req['soundcloud_page'])
            self.assertEqual(artist.youtube_channel, some_update_req['youtube_channel'])

            self.assertEqual(response.data["id"], artist.id)
            self.assertEqual(response.data["name"], artist.name)
            self.assertEqual(
                response.data["role"], dict(UserArtistRole.TYPE_CHOICES)[role]
            )
            self.assertEqual(response.data["owner"]["id"], artist_owner.id)
            for some_key in some_update_req:
                self.assertEqual(response.data[some_key], some_update_req[some_key])

    def test_valid_social_media_tiktok_name_edit(self):
        valid_tiktok_names = [None, "testuser", "test.user", "TEST..UsER", "test_U.er1"]

        artist_owner = UserFactory()
        artist = artist_owner.create_artist_v2(name="OtherArtist")
        UserArtistRoleFactory(user=self.user, artist=artist, type=UserArtistRole.OWNER)

        for tiktok_name in valid_tiktok_names:
            url = f'/api/artists/{artist.pk}/social_media/'
            response = self.client.post(
                url, {"tiktok_name": tiktok_name}, format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            artist.refresh_from_db()
            self.assertEqual(artist.tiktok_name, tiktok_name)

    def test_invalid_social_media_tiktok_name_edit(self):
        valid_tiktok_names = [
            -123,
            [],
            {},
            "",
            "s",
            "LongUsernameThatShouldFail",
            "special-character",
            "special)character",
            "special#character",
            "special?character",
            "special*character",
            "@specialcharacter",
        ]

        artist_owner = UserFactory()
        artist = artist_owner.create_artist_v2(name="OtherArtist")
        UserArtistRoleFactory(user=self.user, artist=artist, type=UserArtistRole.OWNER)

        for tiktok_name in valid_tiktok_names:
            url = f'/api/artists/{artist.pk}/social_media/'
            response = self.client.post(
                url, {"tiktok_name": tiktok_name}, format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_artists_by_spotify_id_returns_correct_artists(self):
        url = reverse('artist-search')
        spotify_id = 'xxxxx'

        artist1 = Artistv2Factory(owner=UserFactory(), spotify_id=spotify_id)
        artist2 = Artistv2Factory(owner=UserFactory(), spotify_id=spotify_id)
        Artistv2Factory(owner=UserFactory(), spotify_id='different-id')
        Artistv2Factory(owner=UserFactory(), spotify_id=None)

        response = self.client.get(url, {'spotify_id': spotify_id})
        data = sorted(response.data, key=lambda i: i['id'])

        assert len(data) == 2
        assert data[0]['id'] == artist1.id
        assert data[1]['id'] == artist2.id
        assert data[0]['spotify_id'] == artist1.spotify_id
        assert data[1]['spotify_id'] == artist2.spotify_id
        # Make sure that rest of the artist data is returned in the response.
        self.assertEqual(data[0]['name'], artist1.name)
        self.assertEqual(data[0]['apple_id'], artist1.apple_id)
        self.assertEqual(data[0]['has_owner'], artist1.has_owner)
        self.assertEqual(
            data[0]['created'], artist1.created.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        )
        self.assertEqual(data[0]['spotify_image'], artist1.spotify_image)

        # Making sure that all the social links are not in the response data.
        self.assertNotIn('spotify_page', data[0])
        self.assertNotIn('twitter_name', data[0])
        self.assertNotIn('facebook_page', data[0])
        self.assertNotIn('instagram_name', data[0])
        self.assertNotIn('soundcloud_page', data[0])
        self.assertNotIn('youtube_channel', data[0])

    def test_search_artists_without_spotify_id_returns_error(self):
        url = reverse('artist-search')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_artists_with_unsupported_api_version_returns_error(self):
        url = reverse('artist-search')
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_artists_with_no_results_returns_404(self):
        url = reverse('artist-search')
        response = self.client.get(url, {'spotify_id': 'does-not-exist'})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_related_artists_with_unsupported_api_version_returns_error(self):
        url = reverse('related-artists')
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})

    def test_related_artists_without_artist_id_returns_missing_query_parmeters_error(
        self,
    ):
        url = reverse('related-artists')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(), {'detail': 'Artist ID is missing from query parameters.'}
        )

    def test_related_artists_returns_error_when_artist_doesnt_have_related_song_roles(
        self,
    ):
        url = reverse('related-artists')
        artist_id = '123'

        response = self.client.get(url, {'artist_id': artist_id})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_related_artists_returns_error_when_artist_doesnt_have_contributor_artists(
        self,
    ):
        url = reverse('related-artists')
        artist = Artistv2Factory()
        song = SongFactory()
        SongArtistRoleFactory(artist=artist, song=song)

        response = self.client.get(url, {'artist_id': artist.id})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_related_artists_returns_artists(self):
        url = reverse('related-artists')

        artist_1 = Artistv2Factory()
        artist_2 = Artistv2Factory()
        artist_3 = Artistv2Factory()
        artist_4 = Artistv2Factory()
        artist_5 = Artistv2Factory()

        song_1 = SongFactory()
        song_2 = SongFactory()
        song_3 = SongFactory()
        song_4 = SongFactory()
        song_5 = SongFactory()

        # artist_1 contributed to song_1.
        SongArtistRoleFactory(artist=artist_1, song=song_1)
        # artist_2 contributed with artist_1 to song_1.
        SongArtistRoleFactory(artist=artist_2, song=song_1)
        # artist_5 contributed to song 1 but with role writer so it will not be
        # included.
        SongArtistRoleFactory(
            artist=artist_4, song=song_1, role=SongArtistRole.ROLE_WRITER
        )

        # artist_2 contributed to his song_2.
        SongArtistRoleFactory(artist=artist_2, song=song_2)
        # artist_3 contributed to yet third song_3.
        SongArtistRoleFactory(artist=artist_3, song=song_3)

        # artist_1 contributed to song 4.
        SongArtistRoleFactory(artist=artist_1, song=song_4)
        # artist_4 contributed to song 4 with role writer.
        SongArtistRoleFactory(
            artist=artist_4, song=song_4, role=SongArtistRole.ROLE_WRITER
        )
        # artist_4 contributed to song 1 with role not writer so it will be
        # included.
        SongArtistRoleFactory(
            artist=artist_4, song=song_1, role=SongArtistRole.ROLE_MIXER
        )

        # artist_1 contributed to song 5
        SongArtistRoleFactory(artist=artist_1, song=song_5)
        # artist_5 contributed to song 5
        SongArtistRoleFactory(
            artist=artist_5, song=song_5, role=SongArtistRole.ROLE_WRITER
        )
        # artist_5 contributed to song 5 with role not writer so it will be
        # included.
        SongArtistRoleFactory(
            artist=artist_5, song=song_5, role=SongArtistRole.ROLE_MIXER
        )

        # Getting the artists that contributed with artist_1.
        response = self.client.get(url, {'artist_id': artist_1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # We expect 3 artists in return.
        self.assertEqual(len(response.data), 3)
        # artist_2 contributed with artist_1
        reponse_data = sorted(response.json(), key=lambda artist: artist['id'])
        self.assertEqual(reponse_data[0]['id'], artist_2.id)
        self.assertEqual(reponse_data[0]['id'], artist_2.id)
        self.assertEqual(reponse_data[0]['name'], artist_2.name)
        self.assertEqual(reponse_data[0]['spotify_id'], artist_2.spotify_id)
        self.assertEqual(reponse_data[0]['apple_id'], artist_2.apple_id)
        self.assertEqual(reponse_data[0]['has_owner'], artist_2.has_owner)
        self.assertEqual(
            reponse_data[0]['created'],
            artist_2.created.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )
        # artist_4 contributed with artist_1
        self.assertEqual(reponse_data[1]['id'], artist_4.id)
        self.assertEqual(reponse_data[1]['name'], artist_4.name)
        self.assertEqual(reponse_data[1]['spotify_id'], artist_4.spotify_id)
        self.assertEqual(reponse_data[1]['apple_id'], artist_4.apple_id)
        self.assertEqual(reponse_data[1]['has_owner'], artist_4.has_owner)
        self.assertEqual(
            reponse_data[1]['created'],
            artist_4.created.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )

        # artist_4 contributed with artist_1
        self.assertEqual(reponse_data[2]['id'], artist_5.id)
        self.assertEqual(reponse_data[2]['name'], artist_5.name)
        self.assertEqual(reponse_data[2]['spotify_id'], artist_5.spotify_id)
        self.assertEqual(reponse_data[2]['apple_id'], artist_5.apple_id)
        self.assertEqual(reponse_data[2]['has_owner'], artist_5.has_owner)
        self.assertEqual(
            reponse_data[2]['created'],
            artist_5.created.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )

        # Making sure that all the social links are not in the response data.
        self.assertNotIn('spotify_page', response.data[0])
        self.assertNotIn('twitter_name', response.data[0])
        self.assertNotIn('facebook_page', response.data[0])
        self.assertNotIn('instagram_name', response.data[0])
        self.assertNotIn('soundcloud_page', response.data[0])
        self.assertNotIn('youtube_channel', response.data[0])

    def test_search_wrong_api_version_return_400(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)
        url = reverse('artist-search')

        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'detail': 'API version is not supported.'})
