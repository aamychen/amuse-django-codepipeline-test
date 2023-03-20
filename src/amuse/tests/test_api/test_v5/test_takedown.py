from unittest.mock import patch

from django.urls import reverse

from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.base.views.takedown import (
    DISPLAY_CODE_ERROR_TAKEDOWN_IN_PROGRESS,
    DISPLAY_CODE_ERROR_SPLITS,
    DISPLAY_CODE_ERROR_LICENSED_TRACKS,
)
from amuse.models.release_takedown_request import ReleaseTakedownRequest
from amuse.services.takedown import Takedown, TakedownResponse
from amuse.tests.test_api.base import (
    API_V4_ACCEPT_VALUE,
    API_V5_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from users.models.artist_v2 import UserArtistRole
from users.tests.factories import UserFactory
from releases.models import Release
from releases.tests.factories import ReleaseFactory, ReleaseArtistRoleFactory


class TakedownViewTestCase(AmuseAPITestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        super().setUp()
        self.user = UserFactory()
        self.artist = self.user.create_artist_v2('Le test artiste')
        self.release = ReleaseFactory(user=self.user, status=Release.STATUS_DELIVERED)
        self.release_artist_role = ReleaseArtistRoleFactory(
            artist=self.artist, release=self.release
        )
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_ACCEPT=API_V5_ACCEPT_VALUE)
        self.url = reverse('releases-takedown', kwargs={'release_id': self.release.id})

    @patch.object(Takedown, '__init__', return_value=None)
    def test_wrong_api_version_return_400(self, mock_takedown):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

        response = self.client.post(
            self.url, data={'takedown_reason': 'switch_distributor'}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertDictEqual(
            response.json(), {'detail': WrongAPIversionError.default_detail}
        )
        mock_takedown.assert_not_called()

    @patch.object(Takedown, '__init__', return_value=None)
    def test_logged_out_user_gets_401(self, mock_takedown):
        self.client.logout()

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 401)
        mock_takedown.assert_not_called()

    def test_no_takedown_reason(self):
        response = self.client.post(self.url, data={}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_invalid_takedown_reason(self):
        response = self.client.post(
            self.url,
            data={'takedown_reason': 'this_is_not_a_valid_choice'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    @patch.object(Takedown, 'trigger', return_value=TakedownResponse(True))
    @patch.object(Takedown, '__init__', return_value=None)
    def test_owner_user_can_takedown_release(
        self, mock_takedown_init, mock_takedown_trigger
    ):
        response = self.client.post(
            self.url,
            data={'takedown_reason': ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR},
            format='json',
        )
        self.assertEqual(response.status_code, 204)
        mock_takedown_init.assert_called_once_with(
            self.release, self.user, ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR
        )
        mock_takedown_trigger.assert_called_once()

    @patch.object(Takedown, 'trigger', return_value=TakedownResponse(True))
    @patch.object(Takedown, '__init__', return_value=None)
    def test_super_admin_user_can_takedown_release(
        self, mock_takedown_init, mock_takedown_trigger
    ):
        user = UserFactory()
        self.client.force_authenticate(user)
        user_artist_role = UserArtistRole(
            user=user, artist=self.artist, type=UserArtistRole.SUPERADMIN
        )
        user_artist_role.save()

        response = self.client.post(
            self.url,
            data={'takedown_reason': ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR},
            format='json',
        )
        self.assertEqual(response.status_code, 204)
        mock_takedown_init.assert_called_once_with(
            self.release, user, ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR
        )
        mock_takedown_trigger.assert_called_once()

    @patch.object(Takedown, 'trigger', return_value=TakedownResponse(True))
    @patch.object(Takedown, '__init__', return_value=None)
    def test_admin_user_can_takedown_release(
        self, mock_takedown_init, mock_takedown_trigger
    ):
        user = UserFactory()
        self.client.force_authenticate(user)
        user_artist_role = UserArtistRole(
            user=user, artist=self.artist, type=UserArtistRole.ADMIN
        )
        user_artist_role.save()

        response = self.client.post(
            self.url,
            data={'takedown_reason': ReleaseTakedownRequest.REASON_CHANGE_AUDIO},
            format='json',
        )
        self.assertEqual(response.status_code, 204)
        mock_takedown_init.assert_called_once_with(
            self.release, user, ReleaseTakedownRequest.REASON_CHANGE_AUDIO
        )
        mock_takedown_trigger.assert_called_once()

    @patch.object(Takedown, 'trigger', return_value=TakedownResponse(True))
    @patch.object(Takedown, '__init__', return_value=None)
    def test_amuse_staff_user_can_takedown_release(
        self, mock_takedown_init, mock_takedown_trigger
    ):
        user = UserFactory(is_staff=True)
        self.client.force_authenticate(user)

        response = self.client.post(
            self.url,
            data={'takedown_reason': ReleaseTakedownRequest.REASON_CHANGE_AUDIO},
            format='json',
        )
        self.assertEqual(response.status_code, 204)
        mock_takedown_init.assert_called_once_with(
            self.release, user, ReleaseTakedownRequest.REASON_CHANGE_AUDIO
        )
        mock_takedown_trigger.assert_called_once()

    @patch.object(Takedown, '__init__', return_value=None)
    def test_member_user_cannot_takedown_release(self, mock_takedown):
        user = UserFactory()
        self.client.force_authenticate(user)
        user_artist_role = UserArtistRole(
            user=user, artist=self.artist, type=UserArtistRole.MEMBER
        )
        user_artist_role.save()

        response = self.client.post(
            self.url, data={'takedown_reason': 'switch_distributor'}, format='json'
        )
        self.assertEqual(response.status_code, 403)
        mock_takedown.assert_not_called()

    @patch.object(Takedown, '__init__', return_value=None)
    def test_spectator_user_cannot_takedown_release(self, mock_takedown):
        user = UserFactory()
        self.client.force_authenticate(user)
        user_artist_role = UserArtistRole(
            user=user, artist=self.artist, type=UserArtistRole.SPECTATOR
        )
        user_artist_role.save()

        response = self.client.post(
            self.url, data={'takedown_reason': 'switch_distributor'}, format='json'
        )
        self.assertEqual(response.status_code, 403)
        mock_takedown.assert_not_called()

    @patch.object(Takedown, '__init__', return_value=None)
    def test_cannot_takedown_different_users_release(self, mock_takedown):
        user = UserFactory()
        self.client.force_authenticate(user)

        response = self.client.post(
            self.url, data={'takedown_reason': 'switch_distributor'}, format='json'
        )
        self.assertEqual(response.status_code, 403)
        mock_takedown.assert_not_called()

    @patch.object(Takedown, '__init__', return_value=None)
    def test_not_found_release_returns_404(self, mock_takedown):
        url = reverse('releases-takedown', kwargs={'release_id': self.release.id + 999})

        response = self.client.post(
            url, data={'takedown_reason': 'switch_distributor'}, format='json'
        )
        self.assertEqual(response.status_code, 404)
        mock_takedown.assert_not_called()

    @patch.object(
        Takedown,
        'trigger',
        return_value=TakedownResponse(False, TakedownResponse.FAILED_REASON_NOT_LIVE),
    )
    @patch.object(Takedown, '__init__', return_value=None)
    def test_takedown_failed_not_live_release(
        self, mock_takedown_init, mock_takedown_trigger
    ):
        response = self.client.post(
            self.url, data={'takedown_reason': 'switch_distributor'}, format='json'
        )

        mock_takedown_init.assert_called_once_with(
            self.release, self.user, ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR
        )
        mock_takedown_trigger.assert_called_once()
        self.assertEqual(response.status_code, 405)

    @patch.object(
        Takedown,
        'trigger',
        return_value=TakedownResponse(
            False, TakedownResponse.FAILED_REASON_LOCKED_SPLITS
        ),
    )
    @patch.object(Takedown, '__init__', return_value=None)
    def test_takedown_failed_user_with_advance(
        self, mock_takedown_init, mock_takedown_trigger
    ):
        response = self.client.post(
            self.url,
            data={'takedown_reason': ReleaseTakedownRequest.REASON_CHANGE_ISRC},
            format='json',
        )

        mock_takedown_init.assert_called_once_with(
            self.release, self.user, ReleaseTakedownRequest.REASON_CHANGE_ISRC
        )
        mock_takedown_trigger.assert_called_once()
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            response.json(),
            response.json()
            | {'display_code': DISPLAY_CODE_ERROR_SPLITS, 'form_url': None},
        )

    @patch.object(
        Takedown,
        'trigger',
        return_value=TakedownResponse(
            False, TakedownResponse.FAILED_REASON_LICENSED_TRACKS
        ),
    )
    @patch.object(Takedown, '__init__', return_value=None)
    def test_takedown_failed_with_licensed_tracks(
        self, mock_takedown_init, mock_takedown_trigger
    ):
        response = self.client.post(
            self.url,
            data={'takedown_reason': ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR},
            format='json',
        )

        mock_takedown_init.assert_called_once_with(
            self.release, self.user, ReleaseTakedownRequest.REASON_SWITCH_DISTRIBUTOR
        )
        mock_takedown_trigger.assert_called_once()
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            response.json(),
            response.json()
            | {
                'display_code': DISPLAY_CODE_ERROR_LICENSED_TRACKS,
                'form_url': None,
            },
        )

    @patch.object(
        Takedown,
        'trigger',
        return_value=TakedownResponse(
            False, TakedownResponse.FAILED_REASON_TAKEDOWN_IN_PROGRESS
        ),
    )
    @patch.object(Takedown, '__init__', return_value=None)
    def test_takedown_failed_in_progress(
        self, mock_takedown_init, mock_takedown_trigger
    ):
        response = self.client.post(
            self.url,
            data={'takedown_reason': ReleaseTakedownRequest.REASON_OTHER},
            format='json',
        )

        mock_takedown_init.assert_called_once_with(
            self.release, self.user, ReleaseTakedownRequest.REASON_OTHER
        )
        mock_takedown_trigger.assert_called_once()
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            response.json(),
            response.json()
            | {
                'display_code': DISPLAY_CODE_ERROR_TAKEDOWN_IN_PROGRESS,
                'form_url': None,
            },
        )
