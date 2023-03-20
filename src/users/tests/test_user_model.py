from datetime import timedelta, datetime
from unittest import mock

import responses
from dateutil.relativedelta import relativedelta
from django.conf import global_settings
from django.contrib.auth.hashers import make_password, get_hashers, MD5PasswordHasher
from django.test import TestCase, override_settings
from django.utils import timezone
from googleplaces import GooglePlacesError

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from subscriptions.models import Subscription, SubscriptionPlan
from subscriptions.models import SubscriptionManager
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.models import ArtistV2, UserArtistRole, User, UserMetadata
from users.tests.factories import UserFactory, UserMetadataFactory
from payouts.tests.factories import PayeeFactory


class UserModelTestCase(TestCase):
    def test_get_username(self):
        """
        Testing if get_username() returns USERNAME_FIELD (email) from the User Model.
        """
        user = UserFactory(email='kalle@dummymail.se')
        assert user.get_username() == user.email == 'kalle@dummymail.se'

    @override_settings(PASSWORD_HASHERS=global_settings.PASSWORD_HASHERS)
    def test_user_password_hashed_with_pbkdf2(self):
        assert MD5PasswordHasher not in [type(hasher) for hasher in get_hashers()]

        django_hash_algorithm_prefix = 'pbkdf2_sha256$'
        assert make_password('foobar').startswith(django_hash_algorithm_prefix)

    def test_create_artist_v2(self):
        """Test create artist v2 method"""
        artist_data = {
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

        user = UserFactory()
        artist_v2 = user.create_artist_v2(**artist_data)

        # Make sure that artist instance created is v2 instance.
        self.assertTrue(isinstance(artist_v2, ArtistV2))

        # Make sure that all the passed artist data are saved to artistv2
        # instance.
        self.assertEqual(artist_v2.name, artist_data['name'])
        self.assertEqual(artist_v2.spotify_page, artist_data['spotify_page'])
        self.assertEqual(artist_v2.twitter_name, artist_data['twitter_name'])
        self.assertEqual(artist_v2.facebook_page, artist_data['facebook_page'])
        self.assertEqual(artist_v2.instagram_name, artist_data['instagram_name'])
        self.assertEqual(artist_v2.soundcloud_page, artist_data['soundcloud_page'])
        self.assertEqual(artist_v2.youtube_channel, artist_data['youtube_channel'])
        self.assertEqual(artist_v2.spotify_id, artist_data['spotify_id'])
        self.assertEqual(artist_v2.apple_id, artist_data['apple_id'])

        # Fetch the UserArtistRole insatnce that belongs to the artist.
        user_artist_role = UserArtistRole.objects.get(artist=artist_v2)

        # Make sure the UserArtistRole insatnce has the same user.
        self.assertEqual(user_artist_role.user, user)
        # Make sure that UserArtistRole insatnce type is owner.
        self.assertEqual(user_artist_role.type, UserArtistRole.OWNER)

    def test_has_artist_with_spotify_id(self):
        user = UserFactory()
        user.create_artist_v2("Artist")

        assert not user.has_artist_with_spotify_id()

        user.create_artist_v2("Spotify Artist", spotify_id='123')
        assert user.has_artist_with_spotify_id()

    def test_main_artist_profile(self):
        user = UserFactory()
        artist = user.create_artist_v2(name='artist')

        self.assertIsNone(user.main_artist_profile)

        user.userartistrole_set.filter(user=user, artist=artist).update(
            main_artist_profile=True
        )

        self.assertEqual(user.main_artist_profile, artist.id)

    def test_token_is_rotated_on_password_change(self):
        user = UserFactory()

        assert user.password
        assert user.auth_token.key

        old_auth_token = user.auth_token.key

        user.set_password("foobarbaz")
        user.save()

        user.refresh_from_db()

        assert user.auth_token.key != old_auth_token

    def test_token_not_rotated_on_set_unusable_password(self):
        user = UserFactory()

        assert user.password
        assert user.auth_token.key

        old_auth_token = user.auth_token.key

        user.set_unusable_password()
        user.save()

        user.refresh_from_db()

        assert user.auth_token.key == old_auth_token

    def test_usermetadata_flagged_reason_display(self):
        metadata = UserMetadataFactory()
        display = metadata.flagged_reason_display
        self.assertRaises(Exception, metadata.flagged_reason)
        assert display == None
        metadata.flagged_reason = UserMetadata.FLAGGED_REASON_SCAM
        metadata.save()
        display = metadata.flagged_reason_display
        assert display != None
        assert 'Scam' in display

    def test_get_flagged_reason(self):
        user = UserFactory()
        # Metadata does not exit case
        reason = user.get_flagged_reason()
        self.assertIsNone(reason)
        # Metadata exist but flagged_reason not set
        metadata = UserMetadataFactory(user=user)
        reason = user.get_flagged_reason()
        self.assertIsNone(reason)
        # Metadata exist and flagged_reason s set
        metadata.flagged_reason = UserMetadata.FLAGGED_REASON_RESTRICTED_COUNTRY
        metadata.save()
        reason = user.get_flagged_reason()
        self.assertIsNotNone(reason)
        assert 'country' in reason

    def test_is_user_account_delete_requested(self):
        deleted_user = UserFactory()
        UserMetadataFactory(
            user=deleted_user,
            is_delete_requested=True,
            delete_requested_at=datetime.now(),
        )
        user = UserFactory()

        self.assertTrue(deleted_user.is_delete_requested)
        self.assertFalse(user.is_delete_requested)

    def test_flag_for_delete(self):
        user = UserFactory()
        UserMetadataFactory(
            user=user, is_delete_requested=False, delete_requested_at=None
        )

        user.flag_for_delete()

        user.refresh_from_db()
        self.assertTrue(user.usermetadata.is_delete_requested)
        self.assertIsNotNone(user.usermetadata.delete_requested_at)

    def test_flag_for_delete_usermetadata_does_not_exist(self):
        user = UserFactory()

        user.flag_for_delete()

        user.refresh_from_db()
        self.assertTrue(user.usermetadata.is_delete_requested)
        self.assertIsNotNone(user.usermetadata.delete_requested_at)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class UserIsProCacheTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.sub = SubscriptionFactory(user=self.user)

    @mock.patch.object(SubscriptionManager, 'active')
    def test_is_pro_cached(self, mock_sub_active):
        # execute is_pro (get value from the db)
        self.assertTrue(self.user.is_pro)
        self.assertEqual(1, mock_sub_active.call_count)

        # execute is_pro (get value from the cache)
        self.assertTrue(self.user.is_pro)
        self.assertEqual(1, mock_sub_active.call_count)

        # clear the cache and check is_pro (get value from the db)
        del self.user.is_pro
        self.assertTrue(self.user.is_pro)

    @mock.patch.object(SubscriptionManager, 'active')
    def test_is_pro_cache_cleared_on_subscription_save(self, mock_sub_active):
        # execute is_pro (get value from the db)
        self.assertTrue(self.user.is_pro)
        self.assertEqual(1, mock_sub_active.call_count)

        # execute is_pro (get value from the cache)
        self.assertTrue(self.user.is_pro)

        # update the sub (it should clear the cache with a post_save event)
        self.sub.valid_until = timezone.now().date() + relativedelta(months=1)
        self.sub.save()

        self.assertTrue(self.user.is_pro)
        self.assertEqual(2, mock_sub_active.call_count)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class UserHasSubscriptionForDateTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.date = timezone.now().date()

    def test_no_end_date_returns_true(self):
        SubscriptionFactory(user=self.user)

        assert self.user.has_subscription_for_date(self.date)
        assert self.user.is_pro

    def test_future_end_date_returns_true(self):
        SubscriptionFactory(user=self.user, valid_from=self.date, valid_until=self.date)

        assert self.user.has_subscription_for_date(self.date)

    def test_end_date_passed_returns_false(self):
        SubscriptionFactory(
            user=self.user,
            valid_until=self.date - timedelta(days=5),
            status=Subscription.STATUS_EXPIRED,
        )

        assert not self.user.has_subscription_for_date(self.date)

    def test_no_subscription_returns_false(self):
        assert not self.user.has_subscription_for_date(self.date)
        assert not self.user.is_pro

    def test_subscription_with_created_status_returns_false(self):
        SubscriptionFactory(
            user=self.user,
            valid_from=self.date,
            valid_until=self.date,
            status=Subscription.STATUS_CREATED,
        )
        assert not self.user.has_subscription_for_date(self.date)
        assert not self.user.is_pro

    def test_subscription_in_grace_period_returns_true(self):
        SubscriptionFactory(
            user=self.user,
            valid_from=self.date,
            valid_until=self.date - timedelta(days=5),
            grace_period_until=self.date + timedelta(days=5),
            status=Subscription.STATUS_GRACE_PERIOD,
        )
        assert self.user.has_subscription_for_date(self.date)
        assert self.user.is_pro


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestUserTierProperty(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()

    def test_free_user_case(self):
        self.assertEqual(self.user.tier, 0)
        self.assertEqual(
            self.user.get_tier_for_date(datetime.now().date()), User.TIER_FREE
        )
        self.assertEqual(
            self.user.get_tier_display_for_date(datetime.now().date()), 'Free Tier'
        )

    def test_plus_user_case(self):
        sub_plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS)
        SubscriptionFactory(user=self.user, plan=sub_plan)
        assert self.user.tier == SubscriptionPlan.TIER_PLUS
        self.assertEqual(
            self.user.get_tier_for_date(datetime.now().date()),
            SubscriptionPlan.TIER_PLUS,
        )
        self.assertEqual(
            self.user.get_tier_display_for_date(datetime.now().date()),
            sub_plan.get_tier_display(),
        )

    def test_pro_user_case(self):
        sub_plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PRO)
        SubscriptionFactory(user=self.user, plan=sub_plan)
        assert self.user.tier == SubscriptionPlan.TIER_PRO
        self.assertEqual(
            self.user.get_tier_for_date(datetime.now().date()),
            SubscriptionPlan.TIER_PRO,
        )
        self.assertEqual(
            self.user.get_tier_display_for_date(datetime.now().date()),
            sub_plan.get_tier_display(),
        )


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class UserIsFreeTrialActive(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.date = timezone.now().date()

    def test_user_is_free_trial(self):
        sub = SubscriptionFactory(
            user=self.user,
            free_trial_from=timezone.now() - timedelta(days=5),
            free_trial_until=timezone.now() + timedelta(days=5),
        )
        self.assertTrue(self.user.is_free_trial_active())

    def test_user_is_not_free_trial(self):
        sub = SubscriptionFactory(user=self.user)
        self.assertFalse(self.user.is_free_trial_active())

    def test_user_with_no_subscription_is_not_free_trial(self):
        self.assertFalse(self.user.is_free_trial_active())


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class UserIsFreeTrialEligibleTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.date = timezone.now().date()

    def test_user_is_eligible(self):
        self.assertTrue(self.user.is_free_trial_eligible())

        sub = SubscriptionFactory(user=self.user)
        self.assertTrue(self.user.is_free_trial_eligible())

    def test_user_is_not_eligible(self):
        sub = SubscriptionFactory(
            user=self.user,
            free_trial_from=timezone.now() - timedelta(days=5),
            free_trial_until=timezone.now() + timedelta(days=5),
        )
        self.assertFalse(self.user.is_free_trial_eligible())


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class UserHyperwalletIntegrationTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory(country='TR')
        self.metadata = UserMetadataFactory(user=self.user)

    def test_user_is_hw_direct(self):
        # Assert all users have "direct" flag for hyperwallet_integration
        self.assertEqual(self.user.hyperwallet_integration, "direct")

    def test_payee_profile_exist(self):
        assert self.user.payee_profile_exist == False
        PayeeFactory(user=self.user)
        assert self.user.payee_profile_exist == True


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class UserEmailVerifiedTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory(country='TR', email_verified=True)

    def test_user_email_verified_is_updated(self):
        self.assertTrue(self.user.email_verified)
        self.user.email = "foo@example.com"
        self.user.save()

        self.assertFalse(self.user.email_verified)

    @mock.patch("amuse.tasks.send_email_verification_email.delay")
    def test_email_not_changed_verified_not_updated(
        self, mock_send_verification_email_delay
    ):
        self.assertTrue(self.user.email_verified)
        self.user.first_name = "New name"
        self.user.save()

        self.user.refresh_from_db()

        self.assertEqual(self.user.first_name, "New name")
        self.assertTrue(self.user.email_verified)
        mock_send_verification_email_delay.assert_not_called()


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class UserPostCreatedActionsTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()

    @override_settings(DJANGO_DEBUG=False)
    @mock.patch("amuse.tasks.post_slack_user_created.delay")
    @mock.patch("amuse.tasks.send_email_verification_email.delay")
    @mock.patch("amuse.tasks.zendesk_create_or_update_user.delay")
    def test_user_created_successful(
        self, mock_zendesk, mock_email_verification, mock_slack
    ):
        user2 = UserFactory()

        self.assertIsNotNone(user2.auth_token)

        mock_zendesk.assert_called_once()
        mock_email_verification.assert_called_once()
        mock_slack.assert_called_once()

    @override_settings(DJANGO_DEBUG=False)
    @mock.patch("amuse.tasks.zendesk_create_or_update_user.delay")
    def test_user_updated_with_zendesk_id(self, mock_zendesk):
        self.user.zendesk_id = "123456"
        self.user.save()

        mock_zendesk.assert_called_once()

    @mock.patch("amuse.places.get_country_by_place_id", return_value='KZ')
    def test_user_created_without_country(self, mock_google_get_country):
        user2 = UserFactory(country=None)

        user2.refresh_from_db()

        mock_google_get_country.assert_called_once()
        self.assertIsNotNone(user2.country)
        self.assertEqual(user2.country, 'KZ')

    @mock.patch("amuse.logging.logger.error")
    @mock.patch("amuse.places.get_country_by_place_id", side_effect=GooglePlacesError)
    def test_user_created_without_country_google_error(
        self, mock_google_get_country, mock_logger
    ):
        user2 = UserFactory(country=None)

        mock_google_get_country.assert_called_once()
        mock_logger.assert_called_once_with(
            f"GooglePlacesError for place_id: %s", user2.place_id
        )
