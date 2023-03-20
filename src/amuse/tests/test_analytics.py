from datetime import timedelta
from unittest.mock import patch

import responses
from django.test import TestCase, RequestFactory
from django.utils import timezone
from freezegun import freeze_time

from amuse.analytics import (
    get_device,
    subscription_trial_started,
    rb_successful,
    segment_release_approved,
    segment_release_not_approved,
    segment_release_rejected,
    segment_release_taken_down,
    segment_release_deleted,
    segment_release_delivered,
    segment_release_undeliverable,
    segment_release_released,
    signup_completed,
    user_requested_account_delete,
    subscription_canceled,
    subscription_tier_upgraded,
    subscription_payment_method_changed,
    user_frozen,
    s4a_connected,
)
from amuse.platform import PlatformType
from countries.tests.factories import CountryFactory
from releases.models import Release, ReleaseArtistRole
from releases.tests.factories import ReleaseFactory, ReleaseArtistRoleFactory
from subscriptions.models import SubscriptionPlan
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.tests.factories import AppsflyerDeviceFactory, UserFactory, Artistv2Factory


class TestCaseMostRecentDevice(TestCase):
    @responses.activate
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_use_most_recent_device(self, mock_zendesk):
        user = UserFactory()

        with freeze_time("2020-01-10"):
            device_recent = AppsflyerDeviceFactory(appsflyer_id='123', user=user)

        with freeze_time("2002-01-10"):
            device_older = AppsflyerDeviceFactory(appsflyer_id='124', user=user)

        device = get_device(user.id)
        self.assertEqual(device.appsflyer_id, device_recent.appsflyer_id)

    @responses.activate
    @patch('amuse.vendor.appsflyer.events.subscription_trial_started')
    @patch('amuse.vendor.segment.events.subscription_trial_started')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_trial_started(self, _, mock_segment, mock_af):
        user = UserFactory()
        subscription = SubscriptionFactory(user=user)
        device = AppsflyerDeviceFactory(appsflyer_id='123', user=user)

        subscription_trial_started(subscription, PlatformType.ANDROID, '', None, 'USD')

        mock_segment.assert_called_once_with(subscription, '', None, 'USD')
        mock_af.assert_called_once_with(device, subscription, None, country='USD')


class TestAnalytics(TestCase):
    def setUp(self) -> None:
        self.country = CountryFactory(code="BA", name="Bosnia and Herzegovina")

        self.user = UserFactory(
            first_name="Random Name",
            last_name="Random Last Name",
            country="US",
            email='a392c814@example.com',
            phone='+444423439277',
            phone_verified=True,
        )

        self.artist = UserFactory(
            first_name="Random Artist Name",
            last_name="Random Artist Last Name",
            country="US",
            email='a393242c34814@example.com',
            phone='+444412334455',
            phone_verified=True,
        )

        self.writer = UserFactory(
            first_name="Random Writer Name",
            last_name="Random Writer Last Name",
            country="US",
            email='writc34814@example.com',
            phone='+444413834797',
            phone_verified=True,
        )

        self.owner = UserFactory(is_active=True)
        self.artist_2 = Artistv2Factory(owner=self.owner)
        self.release = ReleaseFactory(
            status=Release.STATUS_PENDING, user=self.owner, created_by=self.owner
        )
        ReleaseArtistRoleFactory(
            artist=self.artist_2,
            release=self.release,
            role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST,
            main_primary_artist=True,
        )

        self.releases_request_body = {
            "artist_id": self.user.id,
            "name": "Some Random Release Name",
            "type": "single",
            "release_date": "2029-09-11",
            "original_release_date": "",
            "label": "",
            "genre": {"id": 1, "name": "Genre"},
            "status": "pending",
            "upc": "",
            "cover_art_filename": "cover.png",
            "cover_art": {
                "id": 170511,
                "file": "https://amuse-cover-art-uploaded-staging.s3.amazonaws.com:443/cover.jpg",
                "filename": "cover.jpg",
                "thumbnail": "https://amuse-cover-art-uploaded-staging.s3.amazonaws.com:443/cover.400x400.jpg",
                "checksum": None,
            },
            "songs": [
                {
                    "name": "Some Random Song Name",
                    "filename": "N/A",
                    "sequence": 2,
                    "recording_year": 1900,
                    "original_release_date": "",
                    "origin": "cover",
                    "explicit": "none",
                    "version": "",
                    "isrc": "TEST12345678",
                    "genre": {"id": 1, "name": "Alternative"},
                    "artists_roles": [
                        {
                            "roles": ["primary_artist", "producer"],
                            "artist_id": self.artist.id,
                        },
                        {"roles": ["writer"], "artist_id": self.writer.id},
                    ],
                    "royalty_splits": [
                        {"rate": 1.0000, "name": "Bak Bak", "user_id": self.user.id}
                    ],
                    "error_flags": {
                        "rights_samplings": False,
                        "rights_remix": False,
                        "rights_no-rights": False,
                        "audio_bad-quality": False,
                        "explicit_lyrics": False,
                        "genre_not-approved": False,
                        "audio_too-short": False,
                        "wrong-isrc": False,
                        "misleading-artist-name": False,
                        "audio_silent-end-beginning": False,
                        "audio_cut-short": False,
                        "audio_continuous-mix": False,
                    },
                    "youtube_content_id": "none",
                    "cover_licensor": "",
                },
                {
                    "name": "Some Random Song Name",
                    "filename": "N/A",
                    "sequence": 2,
                    "recording_year": 1900,
                    "original_release_date": "",
                    "origin": "cover",
                    "explicit": "none",
                    "version": "",
                    "isrc": "TEST12345678",
                    "genre": {"id": 1, "name": "Alternative"},
                    "artists_roles": [
                        {
                            "roles": ["primary_artist", "producer"],
                            "artist_id": self.artist.id,
                        },
                        {"roles": ["writer"], "artist_id": self.writer.id},
                    ],
                    "royalty_splits": [
                        {"rate": 1.0000, "name": "Bak Bak", "user_id": self.user.id}
                    ],
                    "error_flags": {
                        "rights_samplings": False,
                        "rights_remix": False,
                        "rights_no-rights": False,
                        "audio_bad-quality": False,
                        "explicit_lyrics": False,
                        "genre_not-approved": False,
                        "audio_too-short": False,
                        "wrong-isrc": False,
                        "misleading-artist-name": False,
                        "audio_silent-end-beginning": False,
                        "audio_cut-short": False,
                        "audio_continuous-mix": False,
                    },
                    "youtube_content_id": "none",
                    "cover_licensor": "",
                },
            ],
            "featured_artists": [],
            "error_flags": {
                "artwork_social-media": False,
                "artwork_text": False,
                "artwork_format": False,
                "artwork_size": False,
                "artwork_blurry": False,
                "explicit_parental-advisory": False,
                "titles_differs": False,
                "release_date-changed": False,
                "release_duplicate": False,
                "release_underage": False,
                "rights_no-rights": False,
                "release_generic-artist-name": False,
                "release_misleading-artist-name": False,
                "artwork_logos-brands": False,
                "artwork_primary-or-featured": False,
                "artwork_generic": False,
                "artwork_size-new": False,
                "artwork_pa-logo-mismatch": False,
                "metadata_symbols-or-emoji": False,
                "metadata_symbols-emoji-info": False,
                "metadata_generic-terms": False,
                "compound-artist": False,
            },
            "excluded_countries": ["NO", "DK"],
            "excluded_stores": [],
        }

    @patch("amuse.vendor.appsflyer.events.signup_completed")
    @patch("amuse.vendor.segment.events.signup_completed")
    @patch("amuse.vendor.segment.events.identify_user")
    def test_signup_completed_success(
        self, mock_segment_identify_event, mock_segment_signup_event, mock_af_event
    ):
        platform_name = 'web'
        country = 'Congo, Democratic Republic of'
        signup_path = 'regular'
        device = AppsflyerDeviceFactory(appsflyer_id='123', user=self.user)

        signup_completed(self.user, platform_name, country, signup_path)

        mock_segment_identify_event.assert_called_once_with(self.user, platform_name)
        mock_segment_signup_event.assert_called_once_with(
            self.user.id, platform_name, country, signup_path
        )
        mock_af_event.assert_called_once_with(
            device, self.user.id, platform_name, country, signup_path
        )

    @patch("amuse.vendor.appsflyer.events.rb_successful")
    @patch("amuse.vendor.segment.events.send_rb_successful")
    def test_rb_successful_triggered_success(self, mock_segment_event, mock_af_event):
        user_id = 123
        headers = {
            'HTTP_X_TRIGGER_EVENT': '1',
            'HTTP_CF_IPCOUNTRY': 'BA',
            'HTTP_X_USER_AGENT': 'amuse-web/7adf860;',
        }
        self.request = RequestFactory().post(
            f'releases/', self.releases_request_body, **headers
        )

        event_data = {
            "release_id": 555,
            "release_name": "Test Release",
            "main_primary_artist": "Famous Artist",
            "release_date": timezone.now().date() + timedelta(days=10),
        }

        rb_successful(user_id, self.request, event_data)

        mock_segment_event.assert_called_once()
        mock_af_event.assert_called_once()

    @patch("amuse.vendor.appsflyer.events.rb_successful")
    @patch("amuse.vendor.segment.events.send_rb_successful")
    def test_rb_successful_not_triggered_empty_request(
        self, mock_segment_event, mock_af_event
    ):
        user_id = 123
        self.request = None

        event_data = {
            "release_id": 555,
            "release_name": "Test Release",
            "main_primary_artist": "Famous Artist",
            "release_date": timezone.now().date() + timedelta(days=10),
        }

        rb_successful(user_id, self.request, event_data)

        mock_segment_event.assert_not_called()
        mock_af_event.assert_not_called()

    @patch("amuse.vendor.appsflyer.events.rb_successful")
    @patch("amuse.vendor.segment.events.send_rb_successful")
    def test_rb_successful_not_triggered_event_header_does_not_exist(
        self, mock_segment_event, mock_af_event
    ):
        user_id = 123
        headers = {'HTTP_CF_IPCOUNTRY': 'BA', 'HTTP_X_USER_AGENT': 'amuse-web/7adf860;'}
        self.request = RequestFactory().post(
            f'releases/', self.releases_request_body, **headers
        )
        event_data = {
            "release_id": 555,
            "release_name": "Test Release",
            "main_primary_artist": "Famous Artist",
            "release_date": timezone.now().date() + timedelta(days=10),
        }

        rb_successful(user_id, self.request, event_data)

        mock_segment_event.assert_not_called()
        mock_af_event.assert_not_called()

    @patch("amuse.vendor.appsflyer.events.rb_successful")
    @patch("amuse.vendor.segment.events.send_rb_successful")
    def test_rb_successful_not_triggered_event_header_not_equal_1(
        self, mock_segment_event, mock_af_event
    ):
        user_id = 123
        headers = {
            'HTTP_X_TRIGGER_EVENT': '3',
            'HTTP_CF_IPCOUNTRY': 'BA',
            'HTTP_X_USER_AGENT': 'amuse-web/7adf860;',
        }
        self.request = RequestFactory().post(
            f'users/', self.releases_request_body, **headers
        )
        event_data = {
            "release_id": 555,
            "release_name": "Test Release",
            "main_primary_artist": "Famous Artist",
            "release_date": timezone.now().date() + timedelta(days=10),
        }

        rb_successful(user_id, self.request, event_data)

        mock_segment_event.asser_not_called()
        mock_af_event.assert_not_called()

    @patch("amuse.vendor.segment.events.send_release_approved")
    def test_segment_release_approved_triggered_success(self, mock_event):
        self.release.status = Release.STATUS_APPROVED
        self.release.save()

        segment_release_approved(self.release)

        mock_event.assert_called_once()

    @patch("amuse.vendor.segment.events.send_release_not_approved")
    def test_segment_release_not_approved_triggered_success(self, mock_event):
        self.release.status = Release.STATUS_NOT_APPROVED
        self.release.save()

        segment_release_not_approved(self.release)

        mock_event.assert_called_once()

    @patch("amuse.vendor.segment.events.send_release_rejected")
    def test_segment_release_rejected_triggered_success(self, mock_event):
        self.release.status = Release.STATUS_REJECTED
        self.release.save()

        segment_release_rejected(self.release)

        mock_event.assert_called_once()

    @patch("amuse.vendor.segment.events.send_release_taken_down")
    def test_segment_release_taken_down_triggered_success(self, mock_event):
        self.release.status = Release.STATUS_TAKEDOWN
        self.release.save()

        segment_release_taken_down(self.release)

        mock_event.assert_called_once()

    @patch("amuse.vendor.segment.events.send_release_deleted")
    def test_segment_release_deleted_triggered_success(self, mock_event):
        self.release.status = Release.STATUS_DELETED
        self.release.save()

        segment_release_deleted(self.release)

        mock_event.assert_called_once()

    @patch("amuse.vendor.segment.events.send_release_delivered")
    def test_segment_release_delivered_triggered_success(self, mock_event):
        self.release.status = Release.STATUS_DELIVERED
        self.release.save()

        segment_release_delivered(self.release)

        mock_event.assert_called_once()

    @patch("amuse.vendor.segment.events.send_release_undeliverable")
    def test_segment_release_undeliverable_triggered_success(self, mock_event):
        self.release.status = Release.STATUS_UNDELIVERABLE
        self.release.save()

        segment_release_undeliverable(self.release)

        mock_event.assert_called_once()

    @patch("amuse.vendor.segment.events.send_release_released")
    def test_segment_release_released_triggered_success(self, mock_event):
        self.release.status = Release.STATUS_RELEASED
        self.release.save()

        segment_release_released(self.release)

        mock_event.assert_called_once()

    @patch("amuse.vendor.segment.events.user_requested_account_delete")
    def user_requested_account_delete(self, mock_event):
        data = {'a': 1, 'b': 'b'}
        user_requested_account_delete(123, data)

        mock_event.assert_called_once_with(123, data)

    @patch("amuse.vendor.appsflyer.events.subscription_canceled")
    @patch("amuse.vendor.segment.events.subscription_canceled")
    def test_subscription_cancelled(self, mock_segment_event, mock_af_event):
        subscription = SubscriptionFactory()
        client = 'amuse-web/7adf860'
        ip = '127.0.0.1'

        subscription_canceled(subscription, client, ip)

        mock_segment_event.assert_called_once_with(subscription, client=client, ip=ip)
        device = get_device(subscription.user.id)
        mock_af_event.assert_called_once_with(device, subscription, ip=ip)

    @patch("amuse.vendor.appsflyer.events.subscription_tier_upgraded")
    @patch("amuse.vendor.segment.events.subscription_tier_upgraded")
    def test_subscription_tier_upgraded(self, mock_segment_event, mock_af_event):
        prev_sub_plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        sub_plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PRO)
        subscription = SubscriptionFactory(plan=sub_plan)
        client = 'amuse-web/7adf860'
        ip = '127.0.0.1'
        country = CountryFactory(code="BA", name="Bosnia and Herzegovina")

        subscription_tier_upgraded(subscription, prev_sub_plan, client, ip, country)

        mock_segment_event.assert_called_once_with(
            subscription, prev_sub_plan, client, ip, country=country
        )
        device = get_device(subscription.user.id)
        mock_af_event.assert_called_once_with(
            device, subscription, prev_sub_plan, ip, country=country
        )

    @patch("amuse.vendor.appsflyer.events.subscription_payment_method_changed")
    @patch("amuse.vendor.segment.events.subscription_payment_method_changed")
    def test_subscription_payment_method_changed(
        self, mock_segment_event, mock_af_event
    ):
        subscription = SubscriptionFactory()
        client = 'amuse-web/7adf860'
        ip = '127.0.0.1'

        subscription_payment_method_changed(subscription, client, ip)

        mock_segment_event.assert_called_once_with(subscription, client, ip)
        device = get_device(subscription.user_id)
        mock_af_event.assert_called_once_with(device, subscription, ip)

    @patch("amuse.vendor.segment.events.user_frozen")
    def test_user_frozen(self, mock_segment_event):
        user_frozen(self.user)

        mock_segment_event.assert_called_once_with(self.user)

    @patch("amuse.vendor.appsflyer.events.s4a_connected")
    @patch("amuse.vendor.segment.events.s4a_connected")
    def test_s4a_connected(self, mock_segment_event, mock_af_event):
        s4a_connected(self.owner.id, self.artist_2.id)

        mock_segment_event.assert_called_once_with(self.owner.id, self.artist_2.id)
        device = get_device(self.owner.id)
        mock_af_event.assert_called_once_with(device, self.owner.id, self.artist_2.id)
