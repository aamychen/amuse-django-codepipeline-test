from io import StringIO
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from users.models import Comments, UserGDPR
from users.tests.factories import UserFactory, UserGDPRFactory


class ForcePasswordChangeTestCase(TestCase):
    def setUp(self):
        with patch("amuse.tasks.zendesk_create_or_update_user"):
            self.user = UserFactory(password='hunter2', country='US')

    def test_sets_user_password_to_unusable(self):
        call_command('forcepasswordchange', '--ids', self.user.pk)
        self.user.refresh_from_db()

        self.assertFalse(self.user.has_usable_password())

    def test_mail_sent_if_password_invalidated(self):
        mail.outbox = []

        call_command('forcepasswordchange', '--ids', self.user.pk)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].template_name == 'SECURITY_UPDATES'
        assert mail.outbox[0].recipients() == [self.user.email]
        assert mail.outbox[0].merge_vars == {}

    def test_user_ignored_if_password_already_invalidated(self):
        self.user.set_unusable_password()
        self.user.save()
        mail.outbox = []

        out = StringIO()
        call_command('forcepasswordchange', '--ids', self.user.pk, stdout=out)

        assert len(mail.outbox) == 0
        assert f'User {self.user.id} already has unusable password' in out.getvalue()

    def test_multiple_user_ids_can_be_given(self):
        with patch("amuse.tasks.zendesk_create_or_update_user"):
            users = [UserFactory(password='hunter2', country='US') for x in range(0, 5)]

        call_command('forcepasswordchange', '--ids', *[user.pk for user in users])

        assert len(users) == 5
        for user in users:
            user.refresh_from_db()
            assert user.has_usable_password() is False

    def test_comment_added_to_user(self):
        call_command('forcepasswordchange', '--ids', self.user.pk)
        self.user.refresh_from_db()
        assert 'Automatic password reset' in self.user.comments.text

    def test_comment_added_before_previous_comment_text(self):
        Comments.objects.create(user=self.user, text='Already added comment')

        call_command('forcepasswordchange', '--ids', self.user.pk)

        self.user.refresh_from_db()

        reset_comment_idx = self.user.comments.text.index('Automatic password reset')
        previous_comment_idx = self.user.comments.text.index('Already added comment')

        msg = 'Reset comment should be prepended to the comment'
        assert reset_comment_idx < previous_comment_idx, msg


@pytest.mark.django_db
def test_grdp_delete_remaining_data():
    with patch("amuse.tasks.zendesk_create_or_update_user"):
        staff_user = UserFactory(is_staff=True)
        user_1 = UserFactory(facebook_id='facebook_id')
        user_2 = UserFactory(firebase_token='firebase_token')
        user_3 = UserFactory(zendesk_id=123456)
        user_4 = UserFactory()
    user_gdpr_1 = UserGDPRFactory(user=user_1, initiator=staff_user)
    user_gdpr_2 = UserGDPRFactory(user=user_2, initiator=staff_user)
    user_gdpr_3 = UserGDPRFactory(user=user_3, initiator=staff_user)
    UserGDPR.objects.all().update(
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
        user_apple_signin_id=False,
        user_facebook_id=False,
        user_firebase_token=False,
        user_zendesk_id=False,
        transaction_withdrawals=True,
        user_isactive_deactivation=True,
        user_newsletter_deactivation=True,
        zendesk_data=True,
        segment_data=True,
        fuga_data=True,
    )

    assert not user_gdpr_1.user_apple_signin_id
    assert not user_gdpr_1.user_firebase_token
    assert not user_gdpr_1.user_facebook_id
    assert not user_gdpr_1.user_zendesk_id

    assert not user_gdpr_2.user_apple_signin_id
    assert not user_gdpr_2.user_firebase_token
    assert not user_gdpr_2.user_facebook_id
    assert not user_gdpr_2.user_zendesk_id

    assert not user_gdpr_3.user_apple_signin_id
    assert not user_gdpr_3.user_firebase_token
    assert not user_gdpr_3.user_facebook_id
    assert not user_gdpr_3.user_zendesk_id

    assert UserGDPR.objects.filter(initiator=staff_user).count() == 3

    assert not UserGDPR.check_done(user_id=user_1)
    assert not UserGDPR.check_done(user_id=user_2)
    assert not UserGDPR.check_done(user_id=user_3)

    out = StringIO()
    call_command('gdprdeleteremainingdata', stdout=out)

    assert (
        f'Remaining data for user {user_1.id} was cleaned successfully'
        in out.getvalue()
    )
    assert (
        f'Remaining data for user {user_2.id} was cleaned successfully'
        in out.getvalue()
    )
    assert (
        f'Remaining data for user {user_3.id} was cleaned successfully'
        in out.getvalue()
    )
    assert (
        f'Remaining data for user {user_4.id} was cleaned successfully'
        not in out.getvalue()
    )

    user_1.refresh_from_db()
    assert user_1.apple_signin_id is None
    assert user_1.firebase_token is None
    assert user_1.facebook_id is None
    assert user_1.zendesk_id is None

    user_gdpr_1.refresh_from_db()
    assert user_gdpr_1.user_apple_signin_id
    assert user_gdpr_1.user_firebase_token
    assert user_gdpr_1.user_facebook_id
    assert user_gdpr_1.user_zendesk_id

    user_2.refresh_from_db()
    assert user_2.apple_signin_id is None
    assert user_2.firebase_token is None
    assert user_2.facebook_id is None
    assert user_2.zendesk_id is None

    user_gdpr_2.refresh_from_db()
    assert user_gdpr_2.user_apple_signin_id
    assert user_gdpr_2.user_firebase_token
    assert user_gdpr_2.user_facebook_id
    assert user_gdpr_2.user_zendesk_id

    user_3.refresh_from_db()
    assert user_3.apple_signin_id is None
    assert user_3.firebase_token is None
    assert user_3.facebook_id is None
    assert user_3.zendesk_id is None

    user_gdpr_3.refresh_from_db()
    assert user_gdpr_3.user_apple_signin_id
    assert user_gdpr_3.user_firebase_token
    assert user_gdpr_3.user_facebook_id
    assert user_gdpr_3.user_zendesk_id

    assert UserGDPR.objects.filter(initiator=staff_user).count() == 3

    assert UserGDPR.check_done(user_id=user_1.id)
    assert UserGDPR.check_done(user_id=user_2.id)
    assert UserGDPR.check_done(user_id=user_3.id)
