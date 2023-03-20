import responses

from django.core import mail
from django.test import TestCase, override_settings
from unittest import mock

from amuse.mails import (
    send_base_template,
    send_email_verification,
    send_password_reset,
    send_release_pending,
    send_release_link,
    send_release_upload_failure,
    send_release_template_mail,
    build_release_context,
)
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from releases.tests.factories import (
    CoverArtFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
)
from users.tests.factories import UserFactory, Artistv2Factory
from releases.models import ReleaseArtistRole


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class MailCompositionTestCase(TestCase):
    @mock.patch('amuse.mails.password_reset_token_generator')
    @responses.activate
    def test_password_reset(self, token_generator_mock):
        add_zendesk_mock_post_response()
        token_generator_mock.make_token.return_value = '4zb-442c2eec8e211fb187a1'

        # . Fixed pk for deterministic uid obfuscation.
        user = UserFactory(country='US', pk=1_827_561)

        mail.outbox = []

        send_password_reset(user)

        token_generator_mock.make_token.assert_called_with(user)
        self.assertEqual(mail.outbox[0].template_name, 'PASSWORD_RESET')
        self.assertEqual(mail.outbox[0].recipients(), [user.email])
        self.assertEqual(
            mail.outbox[0].merge_vars,
            {
                user.email: {
                    'URL': 'http://app-dev.amuse.io/password-reset/MTgyNzU2MQ/4zb-442c2eec8e211fb187a1/'
                }
            },
        )

    @mock.patch('amuse.mails.email_verification_token_generator')
    @responses.activate
    def test_email_verification(self, token_generator_mock):
        add_zendesk_mock_post_response()
        token_generator_mock.make_token.return_value = '870555d43c536fea5c17'

        # . Fixed pk for deterministic uid obfuscation.
        user = UserFactory(country='US', pk=4_125_512)

        mail.outbox = []

        send_email_verification(user)

        self.assertEqual(mail.outbox[0].template_name, 'EMAIL_VERIFICATION')
        self.assertEqual(mail.outbox[0].recipients(), [user.email])
        self.assertEqual(
            mail.outbox[0].merge_vars,
            {
                user.email: {
                    'URL': 'http://app-dev.amuse.io/email-verification/NDEyNTUxMg/870555d43c536fea5c17/'
                }
            },
        )

    @responses.activate
    def test_base_template(self):
        add_zendesk_mock_post_response()
        user = UserFactory(country='US')

        mail.outbox = []
        send_base_template(
            'test-sender@example.com',
            user,
            'My test subject!',
            '<div>HTML content for example</div>',
            ['test-bcc1@example.com'],
        )

        self.assertEqual(
            mail.outbox[0].recipients(), [user.email, 'test-bcc1@example.com']
        )
        self.assertEqual(mail.outbox[0].subject, 'My test subject!')
        self.assertEqual(
            mail.outbox[0].global_merge_vars,
            {
                'FNAME': user.first_name,
                'MAIL_CONTENT': '<div>HTML content for example</div>',
            },
        )

    @responses.activate
    def test_release_pending(self):
        add_zendesk_mock_post_response()
        user = UserFactory(country='US')
        release = ReleaseFactory(user=user)
        release.release_date = release.release_date.replace(2015, 6, 10)

        mail.outbox = []
        send_release_pending(release)

        self.assertEqual(mail.outbox[0].template_name, 'SUBMISSION_RECEIVED')
        self.assertEqual(mail.outbox[0].recipients(), [release.user.email])
        self.assertEqual(
            mail.outbox[0].merge_vars,
            {
                release.user.email: {
                    'FNAME': user.first_name,
                    'RELEASE_NAME': release.name,
                    'RELEASE_ID': release.id,
                }
            },
        )

    @responses.activate
    def test_release_link(self):
        add_zendesk_mock_post_response()
        user = UserFactory(country='US')
        release = ReleaseFactory(user=user)

        mail.outbox = []
        send_release_link(release)

        self.assertEqual(mail.outbox[0].template_name, 'RELEASE_LINK')
        self.assertEqual(mail.outbox[0].recipients(), [release.user.email])
        self.assertEqual(
            mail.outbox[0].merge_vars,
            {
                release.user.email: {
                    'FIRST_NAME': user.first_name,
                    'LINK': release.link,
                    'RELEASE_NAME': release.name,
                    'RELEASE_ID': release.id,
                }
            },
        )

    @responses.activate
    def test_release_upload_failure(self):
        add_zendesk_mock_post_response()
        user = UserFactory(country='US')
        release = ReleaseFactory(user=user)

        mail.outbox = []
        send_release_upload_failure(release)

        self.assertEqual(mail.outbox[0].template_name, 'SUBMISSION_UPLOAD_FAILURE')
        self.assertEqual(mail.outbox[0].recipients(), [release.user.email])
        self.assertEqual(
            mail.outbox[0].merge_vars,
            {
                release.user.email: {
                    'FNAME': release.user.first_name,
                    'RELEASE_NAME': release.name,
                    'RELEASE_ID': release.id,
                }
            },
        )

    @mock.patch("amuse.mails.send_template_mail")
    def test_send_release_template_mail_does_not_email_creator_if_same_as_owner(
        self, mocked_send_template_mail
    ):
        template = "SUBMISSION_APPROVED"
        owner = mock.Mock(email="owner@amuse.io")
        release = mock.Mock(user=owner, created_by=owner)
        context_keys = [
            'FNAME',
            'ARTIST_NAME',
            'RELEASE_NAME',
            'RELEASE_DATE',
            'RELEASE_ID',
            'UPC_CODE',
        ]

        send_release_template_mail(template, release, context_keys)

        assert mocked_send_template_mail.call_count == 1
        mocked_send_template_mail.assert_called_once_with(
            template, owner.email, build_release_context(owner, release, context_keys)
        )

    @mock.patch("amuse.mails.send_template_mail")
    def test_send_release_template_mail_only_emails_owner_if_no_creator_exists(
        self, mocked_send_template_mail
    ):
        template = "SUBMISSION_APPROVED"
        owner = mock.Mock(email="owner@amuse.io")
        release = mock.Mock(user=owner, created_by=None)
        context_keys = [
            'FNAME',
            'ARTIST_NAME',
            'RELEASE_NAME',
            'RELEASE_DATE',
            'RELEASE_ID',
            'UPC_CODE',
        ]

        send_release_template_mail(template, release, context_keys)

        assert mocked_send_template_mail.call_count == 1
        mocked_send_template_mail.assert_called_once_with(
            template, owner.email, build_release_context(owner, release, context_keys)
        )

    @mock.patch("amuse.mails.send_template_mail")
    def test_send_release_template_mail_emails_creator_too_if_not_same_as_owner(
        self, mocked_send_template_mail
    ):
        template = "SUBMISSION_RECEIVED"
        owner = mock.Mock(email="owner@amuse.io")
        creator = mock.Mock(email="creator@amuse.io")
        release = mock.Mock(user=owner, created_by=creator)
        context_keys = ['FNAME', 'RELEASE_NAME', 'RELEASE_ID']

        send_release_template_mail(template, release, context_keys)

        assert mocked_send_template_mail.call_count == 2

        creator_context = build_release_context(creator, release, context_keys)
        owner_context = build_release_context(owner, release, context_keys)

        assert sorted(mocked_send_template_mail.call_args_list) == sorted(
            [
                mock.call(template, creator.email, creator_context),
                mock.call(template, owner.email, owner_context),
            ]
        )

    def test_send_release_template_mail_emails_raises_error_on_unsupported_templates(
        self,
    ):
        with self.assertRaises(AssertionError):
            send_release_template_mail("SECURITY_UPDATES", None, None)

    @mock.patch("amuse.mails.send_template_mail")
    def test_send_release_template_mail_sets_correct_template_country(
        self, mocked_send_template_mail
    ):
        template = 'RELEASE_LINK'
        owner = mock.Mock(email="owner@amuse.io", country="US")
        creator = mock.Mock(email="creator@amuse.io", country="MX")
        release = mock.Mock(user=owner, created_by=creator)
        context_keys = ['LINK', 'FIRST_NAME', 'RELEASE_NAME', 'RELEASE_ID']

        send_release_template_mail(template, release, context_keys)

        creator_context = build_release_context(creator, release, context_keys)
        owner_context = build_release_context(owner, release, context_keys)

        assert sorted(mocked_send_template_mail.call_args_list) == sorted(
            [
                mock.call("%s_ES" % template, creator.email, creator_context),
                mock.call(template, owner.email, owner_context),
            ]
        )
