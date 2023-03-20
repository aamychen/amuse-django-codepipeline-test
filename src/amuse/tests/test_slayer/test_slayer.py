import logging
import json
from unittest import mock

import grpclib
import pytest
from django.urls import reverse_lazy as reverse
from rest_framework import status
from rest_framework.test import APITestCase
import pyslayer.exceptions
from pyslayer.services.legacy import (
    ArtistDailySimpleResponse,
    ArtistSongDailySimpleResponse,
)
from pyslayer.services.revenue import (
    ValidateAppRoyaltyAdvanceOfferResponse,
    ActivateAppRoyaltyAdvanceResponse,
    CancelAppRoyaltyAdvanceResponse,
    RefundAppRoyaltyAdvanceResponse,
)
from pyslayer.services.activity import ArtistSummaryResponse
from pyslayer.services.metadata import (
    SpotifyArtistSearchResponse,
    GetReleaseRequest,
    GetReleaseResponse,
)

from amuse.tests.helpers import mock_update_offer, mock_validate_offer
from releases.tests.factories import ReleaseFactory
from slayer.clientwrapper import slayer, get_release_with_license_info
from users.models.user import User
from users.tests.factories import UserFactory, UserArtistRoleFactory, Artistv2Factory

USER_DAILY_MOCK_RESPONSE = {
    'artist_daily': [
        {'user_id': 1, 'date': '1979-01-01', 'streams': 123, 'downloads': 1234}
    ]
}
SONG_DAILY_MOCK_RESPONSE = {
    'artist_song_daily': [
        {'song_id': 123, 'date': '1979-01-01', 'streams': 123, 'downloads': 1234}
    ]
}
ARTIST_SUMMARY_MOCK_RESPONSE = {
    'artist_summary': {
        'artist_id': '111',
        'spotify': {
            'streams_total': '1',
            'streams_7_d': '2',
            'streams_7_d_prev': '3',
        },
        'applemusic': {
            'streams_total': '4',
            'streams_7_d': '5',
            'streams_7_d_prev': '6',
            'most_recent_date': '1980-01-01T00:00:00Z',
        },
        'total': {
            'streams_total': '7',
            'streams_7_d': '8',
            'streams_7_d_prev': '9',
            'most_recent_date': '1990-01-01T00:00:00Z',
        },
    }
}

USER_ACTIVITY_MOCK_RESPONSE = {
    'artist_summary': {
        'artist_id': '222',
        'spotify': {
            'streams_total': '3',
            'streams_7_d': '2',
            'streams_7_d_prev': '1',
            'most_recent_date': '2000-01-01T00:00:00Z',
        },
        'applemusic': {
            'streams_total': '6',
            'streams_7_d': '5',
            'streams_7_d_prev': '4',
            'most_recent_date': '2010-01-01T00:00:00Z',
        },
        'total': {
            'streams_total': '9',
            'streams_7_d': '8',
            'streams_7_d_prev': '7',
            'most_recent_date': '2020-01-01T00:00:00Z',
        },
    }
}

ARTIST_ACTIVITY_MOCK_RESPONSE = {
    'artist_summary': {
        'artist_id': '333',
        'spotify': {
            'streams_total': '2',
            'streams_7_d': '3',
            'streams_7_d_prev': '1',
            'most_recent_date': '2020-01-01T00:00:00Z',
        },
        'applemusic': {
            'streams_total': '5',
            'streams_7_d': '6',
            'streams_7_d_prev': '4',
            'most_recent_date': '2030-01-01T00:00:00Z',
        },
        'total': {
            'streams_total': '8',
            'streams_7_d': '9',
            'streams_7_d_prev': '7',
            'most_recent_date': '2040-01-01T00:00:00Z',
        },
    }
}

RELEASE_WITH_LICENSE_INFO_MOCK_RESPONSE = {
    "release": {
        "id": "43256",
        "upc": "0611056503515",
        "name": "Hex",
        "version": "",
        "release_date": "2018-03-12T00:00:00Z",
        "artist_name": "80purppp",
        "user_id": "37561",
        "status": "RELEASED",
        "contributors": [
            {
                "sequence": 1,
                "role": "PRIMARY_ARTIST",
                "artist_id": "104317",
                "artist_name": "80purppp",
                "artist_ownerId": "37561",
                "main_primaryArtist": False,
            }
        ],
        "active_agreement_ids": ["2379f8aa-f1be-4906-a36f-05fc912bdd38"],
    }
}


class SlayerIntegrationTestCase(APITestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.client.credentials(HTTP_ACCEPT='application/json; version=2')

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistDailySimpleResponse().from_dict(USER_DAILY_MOCK_RESPONSE),
    )
    def test_user_daily_stats_eligible_users(self, mock_uds):
        user = UserFactory(category=User.CATEGORY_QUALIFIED)
        url = reverse('user-user-daily-stats', args=[user.pk])
        self.client.force_authenticate(user=user)
        response = self.client.get(url)

        response_content = dict(
            expected=USER_DAILY_MOCK_RESPONSE['artist_daily'][0],
            actual=response.data[0],
        )
        self.assertDictEqual(response_content["expected"], response_content["actual"])

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistSongDailySimpleResponse().from_dict(
            SONG_DAILY_MOCK_RESPONSE
        ),
    )
    def test_song_daily_stats_ineligible_users(self, mock_uds):
        user = UserFactory(category=User.CATEGORY_DEFAULT)
        url = reverse('user-user-daily-stats', args=[user.pk])
        self.client.force_authenticate(user=user)
        response = self.client.get(url)
        mock_uds.assert_not_called()
        self.assertEqual([], response.data)

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistSongDailySimpleResponse().from_dict(
            SONG_DAILY_MOCK_RESPONSE
        ),
    )
    def test_song_daily_eligible_users(self, mock_sds):
        user = UserFactory(category=User.CATEGORY_QUALIFIED)
        url = reverse('user-song-daily-stats', args=[user.pk])
        self.client.force_authenticate(user=user)
        response = self.client.get(url)

        response_content = dict(
            expected=SONG_DAILY_MOCK_RESPONSE['artist_song_daily'][0],
            actual=response.data[0],
        )

        self.assertDictEqual(response_content["expected"], response_content["actual"])

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistSongDailySimpleResponse().from_dict(
            SONG_DAILY_MOCK_RESPONSE
        ),
    )
    def test_song_daily_ineligible_users(self, mock_sds):
        user = UserFactory(category=User.CATEGORY_DEFAULT)
        url = reverse('user-song-daily-stats', args=[user.pk])
        self.client.force_authenticate(user=user)
        response = self.client.get(url)
        mock_sds.assert_not_called()
        self.assertEqual([], response.data)

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistSummaryResponse().from_dict({}),
        autospec=True,
    )
    def test_summary_not_authorized_404(self, mock_summary):
        user0 = UserFactory()
        user1 = UserFactory()
        url = reverse('user-summary', args=[user1.pk])
        self.client.force_authenticate(user=user0)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mock_summary.assert_not_called()

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistSummaryResponse().from_dict(ARTIST_SUMMARY_MOCK_RESPONSE),
    )
    def test_summary_authorized(self, mock_summary):
        user = UserFactory()
        url = reverse("user-summary", args=[user.pk])
        self.client.force_authenticate(user=user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, ARTIST_SUMMARY_MOCK_RESPONSE)
        self.assertEqual(response.content_type, "application/json")

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=SpotifyArtistSearchResponse().from_dict({"spotify_artists": []}),
    )
    def test_metadata_spotifyartist_not_protected(self, _):
        url = reverse("metadata-artist")
        response = self.client.post(url, {"query": "test"})
        assert response.status_code == status.HTTP_200_OK

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value={},
    )
    def test_metadata_spotifyartist_search_query_is_required(self, _):
        url = reverse("metadata-artist")
        response = self.client.post(url, dict(invalid=123))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @mock.patch(
        "amuse.api.base.views.metadata.metadata_spotifyartist",
        return_value={"spotify_artists": [{"id": "test123"}]},
    )
    def test_metadata_spotifyartist_search_results(self, mock_metadata):
        url = reverse("metadata-artist")
        data = {"query": "test artist"}
        response = self.client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        mock_metadata.assert_called_with(data["query"])
        assert json.loads(response.content) == mock_metadata.return_value

    @mock.patch("amuse.api.base.views.metadata.metadata_spotifyartist", return_value={})
    def test_metadata_spotifyartist_query_can_not_be_empty(self, mock_metadata):
        url = reverse("metadata-artist")
        response = self.client.post(url, {"query": ""})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_metadata.assert_not_called()

    @mock.patch("amuse.api.base.views.metadata.spotify_artist_lookup", return_value={})
    def test_spotify_artist_lookup_not_protected(self, mock_metadata):
        url = reverse("metadata-artist-spotify_id", kwargs={"spotify_id": 'test-123'})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

    @mock.patch(
        "amuse.api.base.views.metadata.spotify_artist_lookup",
        return_value={
            "spotify_artist": [
                {
                    "spotify_artist": {
                        "id": "test-123",
                        "name": "the band",
                        "url": "https://open.spotify.com/artist/test-123",
                        "image_url": "https://i.scdn.co/image/652e2569d818f8187a296e2d3ed6e68a6604561a",
                    }
                }
            ]
        },
    )
    def test_spotify_artist_lookup_search_results(self, mock_metadata):
        url = reverse("metadata-artist-spotify_id", kwargs={"spotify_id": 'test-123'})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert json.loads(response.content) == mock_metadata.return_value

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistDailySimpleResponse().from_dict(USER_DAILY_MOCK_RESPONSE),
    )
    def test_user_daily_stats(self, _):
        user = UserFactory()
        result = slayer.legacy_artist_daily(user.pk)
        self.assertEqual(USER_DAILY_MOCK_RESPONSE['artist_daily'], result)

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistSongDailySimpleResponse().from_dict(
            SONG_DAILY_MOCK_RESPONSE
        ),
    )
    def test_song_daily_stats(self, _):
        user = UserFactory()
        result = slayer.legacy_artist_song_daily(user.pk)
        self.assertEqual(SONG_DAILY_MOCK_RESPONSE['artist_song_daily'], result)

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistSummaryResponse().from_dict(ARTIST_SUMMARY_MOCK_RESPONSE),
    )
    def test_summary(self, _):
        user = UserFactory()
        result = slayer.activity_artist_summary(user.pk)
        self.assertEqual(ARTIST_SUMMARY_MOCK_RESPONSE, result)

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=GetReleaseResponse().from_dict(
            RELEASE_WITH_LICENSE_INFO_MOCK_RESPONSE
        ),
    )
    def test_get_release_with_license_info_ok_response(self, _):
        release = ReleaseFactory()
        response = get_release_with_license_info(release.id)
        assert response.get('release').get('active_agreement_ids') == [
            "2379f8aa-f1be-4906-a36f-05fc912bdd38"
        ]

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistSummaryResponse().from_dict(ARTIST_SUMMARY_MOCK_RESPONSE),
    )
    def test_user_activity_ok_response(self, _):
        user = UserFactory()
        url = reverse("user-activity", args=(user.id, "summary"))
        self.client.force_authenticate(user=user)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == ARTIST_SUMMARY_MOCK_RESPONSE

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value={},
        side_effect=pyslayer.exceptions.SlayerRequestError(
            "Test", None, grpclib.Status.INTERNAL
        ),
    )
    def test_user_activity_failed_response(self, _):
        user = UserFactory()
        url = reverse("user-activity", args=(user.id, "asdf"))
        self.client.force_authenticate(user=user)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value=ArtistSummaryResponse().from_dict(ARTIST_ACTIVITY_MOCK_RESPONSE),
    )
    def test_artist_activity_ok_response(self, _):
        ua = UserArtistRoleFactory()
        url = reverse("artist-activity", args=[ua.artist.id, "summary"])
        self.client.force_authenticate(user=ua.user)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == ARTIST_ACTIVITY_MOCK_RESPONSE

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value={},
        side_effect=pyslayer.exceptions.SlayerRequestError(
            "Test", None, grpclib.Status.UNIMPLEMENTED
        ),
    )
    def test_artist_activity_failed_response(self, _):
        ua = UserArtistRoleFactory()
        url = reverse("artist-activity", args=[ua.artist.id, "updog"])
        self.client.force_authenticate(user=ua.user)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {}

    def test_validate_royalty_advance_offer_success(self):
        user_id = "11"
        offer_id = "xxx"

        mocked_offer = mock_validate_offer(
            user_id=user_id,
            royalty_advance_offer_id=offer_id,
            is_valid=True,
            create_pending_transactions=True,
            split_ids=["1", "2"],
        )

        with mock.patch(
            "pyslayer.SlayerClient.run_in_loop",
            return_value=ValidateAppRoyaltyAdvanceOfferResponse().from_dict(
                mocked_offer
            ),
        ):
            response = slayer.revenue_validate_app_royalty_advance_offer(
                user_id=user_id, offer_id=offer_id, create_pending_transactions=True
            )

        assert response == mocked_offer

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value={},
        side_effect=pyslayer.exceptions.SlayerRequestError(
            "Test", None, grpclib.Status.INTERNAL
        ),
    )
    def test_validate_royalty_advance_offer_failure(self, _):
        user_id = "11"
        offer_id = "xxx"
        with pytest.raises(pyslayer.exceptions.SlayerRequestError) as e:
            slayer.revenue_validate_app_royalty_advance_offer(
                user_id=user_id, offer_id=offer_id, create_pending_transactions=True
            )

        assert e.value.status == grpclib.Status.INTERNAL

    def test_activate_royalty_advance_offer_success(self):
        user_id = "11"
        advance_id = "xxx"
        action = "activate"

        mocked_offer = mock_update_offer(
            user_id=user_id, advance_id=advance_id, action=action, is_valid=True
        )

        with mock.patch(
            "pyslayer.SlayerClient.run_in_loop",
            return_value=ActivateAppRoyaltyAdvanceResponse().from_dict(mocked_offer),
        ):
            response = slayer.update_royalty_advance_offer(
                user_id=user_id,
                advance_id=advance_id,
                action=action,
                description={"blabla": "yadayada"},
            )

        assert response == mocked_offer

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value={},
        side_effect=pyslayer.exceptions.SlayerRequestError(
            "Test", None, grpclib.Status.INTERNAL
        ),
    )
    def test_activate_royalty_advance_offer_failure(self, _):
        user_id = "11"
        advance_id = "xxx"
        action = "activate"

        with pytest.raises(pyslayer.exceptions.SlayerRequestError) as e:
            slayer.update_royalty_advance_offer(
                user_id=user_id, advance_id=advance_id, action=action
            )

        assert e.value.status == grpclib.Status.INTERNAL

    def test_cancel_royalty_advance_offer_success(self):
        user_id = "11"
        advance_id = "xxx"
        action = "cancel"

        mocked_offer = mock_update_offer(
            user_id=user_id, advance_id=advance_id, action=action, is_valid=True
        )

        with mock.patch(
            "pyslayer.SlayerClient.run_in_loop",
            return_value=CancelAppRoyaltyAdvanceResponse().from_dict(mocked_offer),
        ):
            response = slayer.update_royalty_advance_offer(
                user_id=user_id,
                advance_id=advance_id,
                action=action,
                description={"blabla": "yadayada"},
            )

        assert response == mocked_offer

    @mock.patch(
        "pyslayer.SlayerClient.run_in_loop",
        return_value={},
        side_effect=pyslayer.exceptions.SlayerRequestError(
            "Test", None, grpclib.Status.INTERNAL
        ),
    )
    def test_cancel_royalty_advance_offer_failure(self, _):
        user_id = "11"
        advance_id = "xxx"
        action = "cancel"

        with pytest.raises(pyslayer.exceptions.SlayerRequestError) as e:
            slayer.update_royalty_advance_offer(
                user_id=user_id, advance_id=advance_id, action=action
            )

        assert e.value.status == grpclib.Status.INTERNAL

    def test_artist_activity_unauthenticated(self):
        url = reverse("artist-activity", args=[1, "summary"])
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_artist_activity_unauthorized(self):
        user = UserFactory()
        artist = Artistv2Factory()
        url = reverse("artist-activity", args=[artist.id, "summary"])
        self.client.force_authenticate(user=user)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_activity_unauthorized(self):
        url = reverse("user-activity", args=(1, "summary"))
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_activity_authenticated_invalid_user(self):
        user0 = UserFactory()
        user1 = UserFactory()
        self.client.force_authenticate(user=user0)
        url = reverse("user-activity", args=(user1.id, "summary"))
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refund_royalty_advance_offer_success(self):
        user_id: int = 1111
        royalty_advance_id: str = "123-456-3456-8734"

        mocked_response = {
            "user_id": str(1111),
            "royalty_advance_id": "123-456-3456-8734",
            "is_refunded": True,
        }

        with mock.patch(
            "pyslayer.SlayerClient.run_in_loop",
            return_value=RefundAppRoyaltyAdvanceResponse().from_dict(mocked_response),
        ):
            response = slayer.refund_app_royalty_advance(
                user_id=user_id,
                royalty_advance_id=royalty_advance_id,
                refund_amount_currency="USD",
                refund_amount="50",
                description=f"Hyperwallet return {royalty_advance_id}",
                refund_reference=2345,
            )

        assert response == mocked_response
