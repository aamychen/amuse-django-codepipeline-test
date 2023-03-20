from datetime import date, timedelta
from unittest import mock

import responses
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse_lazy as reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework import status

from amuse.storages import S3Storage
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from amuse.tests.test_api.base import API_V4_ACCEPT_VALUE, AmuseAPITestCase
from codes.models import Code
from codes.tests.factories import ISRCFactory, UPCFactory
from countries.tests.factories import CountryFactory
from releases.models import Release, RoyaltySplit, Song, Store, ReleaseArtistRole
from releases.tests.factories import GenreFactory, StoreFactory
from releases.tests.helpers import (
    expected_splits_1,
    expected_splits_1a,
    expected_splits_2,
    expected_splits_3,
    expected_splits_3a,
    expected_splits_4,
    expected_splits_5,
    expected_splits_6,
    expected_splits_7,
)
from users.models import RoyaltyInvitation, User
from users.tests.factories import RoyaltyInvitationFactory, UserFactory
from amuse.tokens import user_invitation_token_generator


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class RoyaltySplitIntegrationTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        with freeze_time("2020-01-15"):
            self.user1 = UserFactory(is_pro=True)
            self.user2 = UserFactory()
            self.user3 = UserFactory()
            self.user4 = UserFactory()

        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user1)
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
        self.invite = {
            'name': 'Artist Name',
            'email': 'artist@example.com',
            'phone_number': '+46723345678',
        }
        self.release_date = timezone.now().date() + timedelta(days=30)

    @responses.activate
    @mock.patch('releases.utils.tasks')
    @mock.patch('amuse.api.v4.serializers.user.fetch_spotify_image', return_value=None)
    @mock.patch(
        "amuse.api.v4.serializers.user.user_profile_photo_s3_url", return_value=None
    )
    @mock.patch("users.helpers.cioevents")
    def test_royalty_split_lifecycle(
        self, mock_tasks, mock_fetch, mock_s3, mock_cioevents
    ):
        self._create_release()

        song = Song.objects.get()
        release = Release.objects.get()
        release.status = Release.STATUS_RELEASED
        release.save()

        # Song starts with inactive multi user splits
        assert self._get_splits_values() == expected_splits_1(
            self.user1.id, self.user2.id
        )

        # Existing user confirms the invitation
        self._confirm_royalty_invitation_by_existing_user(self.user2, release)
        assert self._get_splits_values() == expected_splits_1a(
            self.user1.id, self.user2.id
        )

        # On release day we check if the song has active splits
        with freeze_time(self.release_date):
            call_command("cancel_pending_splits")

        # Revision 1 previous splits have been deleted as song had no active splits
        # and we create a new revision of splits that reallocates the unconfirmed
        # split rate to the creator and we also reclaim revision number 1 in order to
        # enforce serial integrity for split revisions.
        assert self._get_splits_values() == expected_splits_2(
            self.user1.id, self.user2.id
        )

        payload = [
            {'user_id': self.user1.id, 'rate': 0.5},
            {'user_id': self.user2.id, 'rate': 0.4},
            {'invite': self.invite, 'rate': 0.1},
        ]

        # We update the splits
        with freeze_time("2020-03-20"):
            url = reverse("update-royalty-splits", args=(song.id,))
            response = self.client.put(url, payload, format='json')

        invitation_split = RoyaltySplit.objects.get(user__isnull=True)
        invitation = RoyaltyInvitation.objects.get(invitee__isnull=True)
        # TODO BUGFIX needs to fixed in master
        invitation.token = "123"
        invitation.status = RoyaltyInvitation.STATUS_PENDING
        invitation.last_sent = invitation.created
        invitation.save()
        assert response.status_code == status.HTTP_200_OK

        # New inactive split revision 2 is created and revision 1 is still active
        assert self._get_splits_values() == expected_splits_3(
            self.user1.id, self.user2.id
        )

        # Existing user confirms the invitation
        self._confirm_royalty_invitation_by_existing_user(self.user2, release)
        assert self._get_splits_values() == expected_splits_3a(
            self.user1.id, self.user2.id
        )

        # Invited user accepts the split and revision 2 splits are now activated
        with freeze_time("2020-03-21"):
            self._confirm_invitation(invitation)

        invitation.refresh_from_db()

        # Note that revision 2 splits get start_date 2020-03-21 as that was the date
        # the split revision was activated. It does not get the split revision
        # creation start_date 2020-03-20
        assert self._get_splits_values() == expected_splits_4(
            self.user1.id, self.user2.id, invitation.invitee.id
        )

        payload = [
            {'user_id': self.user1.id, 'rate': 0.5},
            {'invite': self.invite, 'rate': 0.5},
        ]

        # We update the splits again
        with freeze_time("2020-05-10"):
            url = reverse("update-royalty-splits", args=(song.id,))
            response = self.client.put(url, payload, format='json')

        # Revision 3 splits are not active so revision 2 splits are still active
        assert self._get_splits_values() == expected_splits_5(
            self.user1.id, self.user2.id, invitation.invitee.id
        )

        payload = [
            {'user_id': self.user1.id, 'rate': 0.5},
            {'user_id': self.user2.id, 'rate': 0.5},
        ]

        # We update the splits again
        with freeze_time("2020-05-12"):
            url = reverse("update-royalty-splits", args=(song.id,))
            response = self.client.put(url, payload, format='json')

        assert self._get_splits_values() == expected_splits_6(
            self.user1.id, self.user2.id, invitation.invitee.id
        )

        # These splits are for existing users so they are activated immediately
        # and we reclaim the revision number 3 from the inactive splits that
        # we delete in order to enforce serial integrity
        # Existing user confirms the invitation
        with freeze_time("2020-05-12"):
            self._confirm_royalty_invitation_by_existing_user(self.user2, release)

        assert self._get_splits_values() == expected_splits_7(
            self.user1.id, self.user2.id, invitation.invitee.id
        )

    def _get_splits_values(self):
        return list(
            RoyaltySplit.objects.all()
            .order_by("revision", "user")
            .values("user_id", "rate", "start_date", "end_date", "status", "revision")
        )

    def _confirm_invitation(self, invitation):
        data = {
            'facebook_access_token': None,
            'google_id_token': None,
            'royalty_token': invitation.token,
            'user_artist_role_token': None,
            **{k: getattr(self.user1, k) for k in self.keys},
        }
        data["email"] = invitation.email
        url = reverse('user-list')
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())

    def _create_release(self):
        country_1 = CountryFactory()
        country_2 = CountryFactory()
        artist_1 = self.user1.create_artist_v2(name='Lil Artist')
        artist_2 = self.user2.create_artist_v2(name='FeaturedArtist')
        artist_3 = self.user3.create_artist_v2(name='WriterArtist')
        artist_4 = self.user4.create_artist_v2(name='ProducerdArtist')

        StoreFactory(name=Store.YOUTUBE_CONTENT_ID_STORE_NAME)
        StoreFactory(internal_name='youtube_music')
        UPCFactory(status=Code.STATUS_UNUSED)
        self.isrc = ISRCFactory(status=Code.STATUS_UNUSED)
        genre = GenreFactory()

        cover_art_storage = S3Storage(
            bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME
        )
        cover_filename = 'cover.jpg'
        with cover_art_storage.open(cover_filename, 'wb') as f:
            f.write(open('amuse/tests/test_api/data/amuse.jpg', 'rb').read())

        request_payload = {
            'name': 'Postman Release (v4)',
            'label': None,
            'cover_art_filename': 'cover.jpg',
            'release_date': self.release_date.isoformat(),
            'excluded_stores': [],
            'excluded_countries': [country_1.code, country_2.code],
            'upc': '',
            'artist_id': artist_1.id,
            'songs': [
                {
                    'name': 'Test Song 1',
                    'sequence': 1,
                    'version': 'Version Title',
                    'explicit': 'clean',
                    'recording_year': 2018,
                    'filename': 'users_filename.wav',
                    'origin': 'remix',
                    'isrc': '',
                    'audio_s3_key': 'wave.wav',
                    'youtube_content_id': 'none',
                    'cover_licensor': '',
                    'genre': {'id': genre.id, 'name': genre.name},
                    'artists_roles': [
                        {'roles': ['mixer', 'writer'], 'artist_id': artist_3.id},
                        {'roles': ['primary_artist'], 'artist_id': artist_1.id},
                        {'roles': ['featured_artist'], 'artist_id': artist_2.id},
                        {'roles': ['producer'], 'artist_id': artist_4.id},
                    ],
                    'royalty_splits': [
                        {'user_id': self.user1.id, 'rate': 0.5},
                        {'user_id': self.user2.id, 'rate': 0.4},
                        {'invite': self.invite, 'rate': 0.1},
                    ],
                }
            ],
        }
        url = reverse('release-list')
        response = self.client.post(url, request_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())

    def _confirm_royalty_invitation_by_existing_user(self, user, release):
        self.client.force_authenticate(user=user)
        invite = (
            RoyaltyInvitation.objects.filter(invitee=user)
            .order_by('-royalty_split_id')
            .first()
        )

        primary_artist_role = ReleaseArtistRole.objects.filter(
            release=release, role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST
        ).first()
        payload = {
            'inviter_id': release.user.id,
            'invitee_id': invite.invitee_id,
            'artist_name': primary_artist_role.artist.name,
            'split_id': invite.royalty_split.id,
        }

        token = user_invitation_token_generator.make_token(payload)

        # simulate sending email to the user
        invite.token = token
        invite.status = RoyaltyInvitation.STATUS_PENDING
        invite.last_sent = timezone.now()
        invite.save()

        # simulate confirm action by user
        url = reverse('royaltyinvitation-confirm')
        data = {'token': invite.token}
        response = self.client.post(url, data, format='json')
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code, response.data)

        self.client.force_authenticate(user=self.user1)
