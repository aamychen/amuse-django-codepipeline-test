from datetime import date
from random import randint
from unittest import mock
from unittest.mock import patch, call

import factory.fuzzy
from django.contrib.admin.models import LogEntry
from django.test import TestCase
from django.utils import timezone
from requests import Response

from amuse import tasks
from amuse.models.minfraud_result import MinfraudResult
from amuse.vendor.fuga.fuga_api import FugaAPIClient
from releases.models.release import Release
from releases.tests.factories import (
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    RoyaltySplitFactory,
    SongArtistRoleFactory,
    SongFactory,
    FugaMetadataFactory,
)
from subscriptions.models import Subscription
from subscriptions.tests.factories import SubscriptionFactory
from users.gdpr import (
    launch_gdpr_tasks,
    delete_releases_from_fuga,
    disable_recurring_adyen_payments,
    delete_user_from_zendesk,
)
from users.models import (
    ArtistV2,
    Transaction,
    TransactionSource,
    TransactionWithdrawal,
    User,
)
from users.models.user import UserGDPR
from users.tests.factories import Artistv2Factory, UserFactory


class TransactionSourceFactory(factory.DjangoModelFactory):
    class Meta:
        model = TransactionSource

    name = factory.Faker('name')


class TransactionFactory(factory.DjangoModelFactory):
    class Meta:
        model = Transaction

    status = Transaction.STATUS_COMPLETED
    type = Transaction.TYPE_DEPOSIT
    amount = factory.fuzzy.FuzzyDecimal(10, 100, precision=12)
    date = factory.fuzzy.FuzzyAttribute(lambda: date.today())
    user = factory.SubFactory(UserFactory)
    source = factory.SubFactory(TransactionSourceFactory)


class TransactionWithdrawalFactory(factory.DjangoModelFactory):
    class Meta:
        model = TransactionWithdrawal

    transaction = factory.SubFactory(
        TransactionFactory, type=Transaction.TYPE_WITHDRAWAL
    )
    name = factory.Faker('name')
    country = factory.Faker('country_code', representation="alpha-2")
    email = factory.Faker('safe_email')
    phone = factory.Faker('phone_number')
    verified = factory.fuzzy.FuzzyChoice([True, False])


class MockResponse:
    def __init__(self, body=None, status=200):
        self.body = body
        self.status_code = status

    def json(self):
        return self.body


class UserGDPRTestCase(TestCase):
    def setUp(self):
        with mock.patch("amuse.tasks.zendesk_create_or_update_user"):
            self.user = UserFactory(newsletter=True, is_active=True)
            self.user.apple_signin_id = 'apple_signin_id'
            self.user.facebook_id = 'facebook_id'
            self.user.firebase_token = 'firebase_token'
            self.user.zendesk_id = 123456789
            self.user.save()

            self.gdpr_removal_initiator = UserFactory(is_staff=True)

        self.gdpr_removal = UserGDPR.objects.create(
            initiator=self.gdpr_removal_initiator, user_id=self.user.id
        )

        self.artist = Artistv2Factory(owner=self.user)

        self.release = ReleaseFactory(type=Release.TYPE_EP, user=self.user)

        ReleaseArtistRoleFactory(artist=self.artist, release=self.release)

        self.song1 = SongFactory(genre=self.release.genre, release=self.release)
        self.song2 = SongFactory(genre=self.release.genre, release=self.release)
        self.song3 = SongFactory(genre=self.release.genre, release=self.release)
        self.song4 = SongFactory(genre=self.release.genre, release=self.release)
        self.song5 = SongFactory(genre=self.release.genre, release=self.release)

        SongArtistRoleFactory(artist=self.artist, song=self.song1)
        SongArtistRoleFactory(artist=self.artist, song=self.song2)
        SongArtistRoleFactory(artist=self.artist, song=self.song3)
        SongArtistRoleFactory(artist=self.artist, song=self.song4)
        SongArtistRoleFactory(artist=self.artist, song=self.song5)

        self.split_1 = RoyaltySplitFactory(user=self.user, song=self.song1)
        RoyaltySplitFactory(user=self.user, song=self.song2)
        RoyaltySplitFactory(user=self.user, song=self.song3)
        RoyaltySplitFactory(user=self.user, song=self.song4)
        RoyaltySplitFactory(user=self.user, song=self.song5)

        random_integer = randint(1, 100)
        MinfraudResult.objects.create(
            user=self.user,
            release=self.release,
            response_body="FraudScore For %s " % self.user.first_name,
            fraud_score=random_integer,
            event_time=timezone.now(),
        )

        self.transaction = TransactionFactory(
            user=self.user, type=Transaction.TYPE_WITHDRAWAL
        )

        self.withdrawal = TransactionWithdrawalFactory(
            transaction=self.transaction,
            name=self.user.name,
            country=self.user.country,
            email=self.user.email,
            phone=self.user.phone,
            verified=True,
        )

    def test_delete_minfraud_entries(self):
        minfrauds = MinfraudResult.objects.filter(user_id=self.user.id)
        assert len(minfrauds) > 0
        tasks.delete_minfraud_entries(self.user.id)
        minfrauds_after_delete = MinfraudResult.objects.filter(user_id=self.user.id)
        assert len(minfrauds_after_delete) == 0
        assert (
            UserGDPR.objects.filter(user_id=self.user.id, minfraud_entries=True).count()
            == 1
        )

    def test_delete_artist_v2_history_entries(self):
        self.artist.name = "Changed Name"
        self.artist.save()

        artist_history = ArtistV2.history.filter(owner_id=self.user.id)

        assert len(artist_history) > 0

        tasks.delete_artist_v2_history_entries(self.user.id)
        artist_history_after_delete = ArtistV2.history.filter(owner_id=self.user.id)
        assert len(artist_history_after_delete) == 0
        assert (
            UserGDPR.objects.filter(
                user_id=self.user.id, artist_v2_history_entries=True
            ).count()
            == 1
        )

    def test_delete_user_history_entries(self):
        LogEntry.objects.create(
            content_type_id=55,
            user_id=self.user.id,
            object_id=self.user.id,
            action_flag=1,
        )

        user_history_entries = LogEntry.objects.filter(
            content_type_id=55, object_id=self.user.id
        )

        assert len(user_history_entries) == 1

        tasks.delete_user_history_entries(self.user.id)

        user_history_entries = LogEntry.objects.filter(
            content_type_id=55, object_id=self.user.id
        )

        assert len(user_history_entries) == 0
        assert (
            UserGDPR.objects.filter(
                user_id=self.user.id, user_history_entries=True
            ).count()
            == 1
        )

    def test_deactivate_user_newsletter_and_active(self):
        tasks.deactivate_user_newsletter_and_active(self.user.id)
        user = User.objects.get(id=self.user.id)
        self.assertFalse(user.newsletter)
        self.assertFalse(user.is_active)
        assert (
            UserGDPR.objects.filter(
                user_id=self.user.id, user_isactive_deactivation=True
            ).count()
            == 1
        )
        assert (
            UserGDPR.objects.filter(
                user_id=self.user.id, user_newsletter_deactivation=True
            ).count()
            == 1
        )

    def test_clean_transaction_withdrawal(self):
        tasks.clean_transaction_withdrawals(self.user.id)
        transactions = Transaction.objects.filter(user=self.user.id)
        for transaction in transactions:
            withdrawals = TransactionWithdrawal.objects.filter(
                transaction_id=transaction.id
            )
            for withdrawal in withdrawals:
                assert withdrawal.name == ""
                self.assertIsNone(withdrawal.address)
                assert withdrawal.country == ""
                self.assertIsNone(withdrawal.email)
                self.assertIsNone(withdrawal.phone)

        assert (
            UserGDPR.objects.filter(
                user_id=self.user.id, transaction_withdrawals=True
            ).count()
            == 1
        )

    def test_clean_artist_data(self):
        tasks.clean_artist_data(self.user.id)

        for artist in ArtistV2.objects.filter(owner=self.user):
            assert artist.name == ""
            self.assertIsNone(artist.image)
            self.assertIsNone(artist.spotify_page)
            self.assertIsNone(artist.twitter_name)
            self.assertIsNone(artist.facebook_page)
            self.assertIsNone(artist.instagram_name)
            self.assertIsNone(artist.soundcloud_page)
            self.assertIsNone(artist.youtube_channel)
            self.assertIsNone(artist.apple_id)
            self.assertIsNone(artist.spotify_id)

        assert (
            UserGDPR.objects.filter(user_id=self.user.id, artist_v2_names=True).count()
            == 1
        )
        assert (
            UserGDPR.objects.filter(
                user_id=self.user.id, artist_v2_social_links=True
            ).count()
            == 1
        )
        assert (
            UserGDPR.objects.filter(user_id=self.user.id, artist_v1_names=True).count()
            == 1
        )
        assert (
            UserGDPR.objects.filter(
                user_id=self.user.id, artist_v1_social_links=True
            ).count()
            == 1
        )

    def test_clean_user_data(self):
        tasks.clean_user_data(self.user.id)
        user = User.objects.get(id=self.user.id)
        assert user.first_name == ""
        assert user.last_name == ""
        assert user.email != self.user.email
        self.assertIsNone(user.artist_name)
        self.assertIsNone(user.apple_id)
        self.assertIsNone(user.spotify_id)
        self.assertIsNone(user.phone)
        self.assertIsNone(user.country)
        self.assertIsNone(user.language)
        self.assertIsNone(user.facebook_id)
        self.assertIsNone(user.google_id)
        self.assertIsNone(user.profile_link)
        self.assertIsNone(user.profile_photo)
        self.assertIsNone(user.zendesk_id)
        self.assertIsNone(user.spotify_page)
        self.assertIsNone(user.twitter_name)
        self.assertIsNone(user.facebook_page)
        self.assertIsNone(user.instagram_name)
        self.assertIsNone(user.soundcloud_page)
        self.assertIsNone(user.youtube_channel)
        self.assertIsNone(user.apple_signin_id)
        self.assertIsNone(user.firebase_token)

        assert (
            UserGDPR.objects.filter(user_id=self.user.id, email_adress=True).count()
            == 1
        )
        assert (
            UserGDPR.objects.filter(user_id=self.user.id, user_first_name=True).count()
            == 1
        )
        assert (
            UserGDPR.objects.filter(user_id=self.user.id, user_last_name=True).count()
            == 1
        )
        assert (
            UserGDPR.objects.filter(
                user_id=self.user.id, user_social_links=True
            ).count()
            == 1
        )
        assert (
            UserGDPR.objects.filter(user_id=self.user.id, user_artist_name=True).count()
            == 1
        )

    def test_user_gdpr_object_created_on_new_id(self):
        with mock.patch("amuse.tasks.zendesk_create_or_update_user"):
            new_user = UserFactory()
        assert UserGDPR.objects.filter(user=new_user).count() == 0
        launch_gdpr_tasks(user=new_user, initiator=self.gdpr_removal_initiator)
        assert UserGDPR.objects.filter(user=new_user).count() == 1

    def test_full_user_gdpr_wipe(self):
        self.assertFalse(self.user.is_gdpr_wiped)

        launch_gdpr_tasks(user=self.user, initiator=self.gdpr_removal_initiator)
        assert (
            UserGDPR.objects.filter(
                user=self.user,
                minfraud_entries=True,
                artist_v2_history_entries=True,
                user_history_entries=True,
                email_adress=True,
                user_first_name=True,
                user_last_name=True,
                user_social_links=True,
                user_artist_name=True,
                artist_v2_names=True,
                artist_v2_social_links=True,
                artist_v1_names=True,
                artist_v1_social_links=True,
                transaction_withdrawals=True,
                user_apple_signin_id=True,
                user_facebook_id=True,
                user_firebase_token=True,
                user_zendesk_id=True,
                user_isactive_deactivation=True,
                user_newsletter_deactivation=True,
            ).count()
            == 1
        )

        self.user.usermetadata.refresh_from_db()
        self.assertTrue(self.user.is_gdpr_wiped)

    def test_full_user_gdpr_wipe_doesnt_wipe_users_with_locked_splits(self):
        self.split_1.is_locked = True
        self.split_1.save()

        launch_gdpr_tasks(user=self.user, initiator=self.gdpr_removal_initiator)
        gdpr_obj = UserGDPR.objects.get(user=self.user)
        assert gdpr_obj.minfraud_entries is False
        assert gdpr_obj.artist_v2_history_entries is False
        assert gdpr_obj.user_history_entries is False
        assert gdpr_obj.email_adress is False
        assert gdpr_obj.user_first_name is False
        assert gdpr_obj.user_last_name is False
        assert gdpr_obj.user_social_links is False
        assert gdpr_obj.user_artist_name is False
        assert gdpr_obj.artist_v2_names is False
        assert gdpr_obj.artist_v2_social_links is False
        assert gdpr_obj.artist_v1_names is False
        assert gdpr_obj.artist_v1_social_links is False
        assert gdpr_obj.transaction_withdrawals is False
        assert gdpr_obj.user_isactive_deactivation is False
        assert gdpr_obj.user_newsletter_deactivation is False

    def test_check_done_returns_false(self):
        UserGDPR.objects.update(
            user=self.user,
            minfraud_entries=True,
            artist_v2_history_entries=True,
            user_history_entries=True,
            email_adress=True,
            user_first_name=False,
            user_last_name=True,
            user_social_links=True,
            user_artist_name=True,
            artist_v2_names=True,
            artist_v2_social_links=True,
            artist_v1_names=True,
            artist_v1_social_links=True,
            transaction_withdrawals=True,
            user_isactive_deactivation=True,
            user_newsletter_deactivation=True,
        )

        assert UserGDPR.check_done(self.user.id) == False

    def test_check_done_returns_true(self):
        UserGDPR.objects.update(
            user=self.user,
            minfraud_entries=True,
            artist_v2_history_entries=True,
            user_history_entries=True,
            email_adress=True,
            user_first_name=True,
            user_last_name=True,
            user_social_links=True,
            user_artist_name=True,
            artist_v2_names=True,
            artist_v2_social_links=True,
            artist_v1_names=True,
            artist_v1_social_links=True,
            user_apple_signin_id=True,
            user_facebook_id=True,
            user_firebase_token=True,
            user_zendesk_id=True,
            transaction_withdrawals=True,
            user_isactive_deactivation=True,
            user_newsletter_deactivation=True,
            zendesk_data=True,
            segment_data=True,
            fuga_data=True,
        )

        self.assertTrue(UserGDPR.check_done(self.user.id))

    @patch.object(FugaAPIClient, 'delete_product', return_value=None)
    def test_delete_releases_from_fuga_multiple_releases(self, mock_fuga_delete):
        release_1 = ReleaseFactory(type=Release.TYPE_EP, user=self.user)
        release_2 = ReleaseFactory(type=Release.TYPE_ALBUM, user=self.user)
        release_3 = ReleaseFactory(type=Release.TYPE_EP, user=self.user)
        fuga_metadata_1 = FugaMetadataFactory(release=release_1)
        fuga_metadata_2 = FugaMetadataFactory(release=release_2)

        delete_releases_from_fuga(self.user.id)

        self.assertEqual(mock_fuga_delete.call_count, 2)
        mock_fuga_delete.assert_has_calls(
            [call(fuga_metadata_1.product_id), call(fuga_metadata_2.product_id)]
        )

    @patch.object(FugaAPIClient, 'delete_product', return_value=None)
    def test_delete_releases_from_fuga_no_releases(self, mock_fuga_delete):
        ReleaseFactory(type=Release.TYPE_EP, user=self.user)

        delete_releases_from_fuga(self.user.id)

        self.assertEqual(mock_fuga_delete.call_count, 0)

    @patch("amuse.tasks.zendesk_create_or_update_user")
    @patch('users.gdpr.disable_recurring_payment')
    def test_disable_recurring_adyen_payments_user_with_active_subscription(
        self, mock_adyen_disable_call, _
    ):
        SubscriptionFactory(user=self.user)

        disable_recurring_adyen_payments(self.user.id)

        self.assertEqual(mock_adyen_disable_call.call_count, 1)

    @patch("amuse.tasks.zendesk_create_or_update_user")
    @patch('users.gdpr.disable_recurring_payment')
    def test_disable_recurring_adyen_payments_user_with_expired_subscription(
        self, mock_adyen_disable_call, _
    ):
        SubscriptionFactory(user=self.user, status=Subscription.STATUS_EXPIRED)

        disable_recurring_adyen_payments(self.user.id)

        self.assertEqual(mock_adyen_disable_call.call_count, 0)

    @patch("amuse.tasks.zendesk_create_or_update_user")
    @patch('users.gdpr.disable_recurring_payment')
    def test_disable_recurring_adyen_payments_user_with_no_subscription(
        self, mock_adyen_disable_call, _
    ):
        disable_recurring_adyen_payments(self.user.id)

        self.assertEqual(mock_adyen_disable_call.call_count, 0)

    @patch("amuse.tasks.zendesk_create_or_update_user")
    @patch('users.gdpr.permanently_delete_user')
    @patch('users.gdpr.delete_ticket')
    @patch(
        'users.gdpr.get_zendesk_tickets_by_user',
        return_value=MockResponse(body={'tickets': [{'id': 22}, {'id': 33}]}),
    )
    @patch(
        'users.gdpr.search_zendesk_users_by_email',
        return_value=MockResponse(body={'users': [{'id': 123}]}),
    )
    def test_delete_user_from_zendesk(
        self,
        mock_search_zendesk,
        mock_get_tickets,
        mock_delete_ticket,
        mock_delete_user,
        _,
    ):
        delete_user_from_zendesk(self.user.id, self.user.email)

        self.assertEqual(mock_search_zendesk.call_count, 1)
        mock_delete_ticket.assert_has_calls([call(22), call(33)])
        mock_delete_user.assert_called_once_with(123)
        assert (
            UserGDPR.objects.filter(user_id=self.user.id, zendesk_data=True).count()
            == 1
        )

    @patch("amuse.tasks.zendesk_create_or_update_user")
    @patch('users.gdpr.permanently_delete_user')
    @patch('users.gdpr.delete_ticket')
    @patch(
        'users.gdpr.get_zendesk_tickets_by_user',
        return_value=MockResponse(body={'tickets': []}),
    )
    @patch(
        'users.gdpr.search_zendesk_users_by_email',
        return_value=MockResponse(body={'users': [{'id': 123}]}),
    )
    def test_delete_user_from_zendesk_no_tickets_found(
        self,
        mock_search_zendesk,
        mock_get_tickets,
        mock_delete_ticket,
        mock_delete_user,
        _,
    ):
        delete_user_from_zendesk(self.user.id, self.user.email)

        self.assertEqual(mock_search_zendesk.call_count, 1)
        self.assertEqual(mock_delete_ticket.call_count, 0)
        mock_delete_user.assert_called_once_with(123)
        assert (
            UserGDPR.objects.filter(user_id=self.user.id, zendesk_data=True).count()
            == 1
        )

    @patch("amuse.tasks.zendesk_create_or_update_user")
    @patch('users.gdpr.permanently_delete_user')
    @patch('users.gdpr.delete_ticket')
    @patch(
        'users.gdpr.search_zendesk_users_by_email',
        return_value=MockResponse(body={'users': []}),
    )
    def test_delete_user_from_zendesk_no_user_found(
        self, mock_search_zendesk, mock_delete_ticket, mock_delete_user, _
    ):
        delete_user_from_zendesk(self.user.id, self.user.email)

        self.assertEqual(mock_search_zendesk.call_count, 1)
        self.assertEqual(mock_delete_ticket.call_count, 0)
        self.assertEqual(mock_delete_user.call_count, 0)
        assert (
            UserGDPR.objects.filter(user_id=self.user.id, zendesk_data=True).count()
            == 1
        )

    @patch("amuse.tasks.zendesk_create_or_update_user")
    @patch('users.gdpr.search_zendesk_users_by_email')
    def test_skip_delete_user_from_zendesk_when_duplicate_email(
        self, mock_search_zendesk, _
    ):
        duplicate_user = UserFactory()
        duplicate_user.email = self.user.email.upper()
        duplicate_user.save()

        delete_user_from_zendesk(self.user.id, self.user.email)

        self.assertEqual(mock_search_zendesk.call_count, 0)
        assert (
            UserGDPR.objects.filter(user_id=self.user.id, zendesk_data=True).count()
            == 1
        )
