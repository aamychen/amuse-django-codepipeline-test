import responses

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings

from amuse.mails import (
    send_base_template,
    send_email_verification,
    send_password_reset,
    send_release_pending,
    send_release_link,
    send_release_upload_failure,
    send_security_update_mail,
)
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from releases.tests.factories import CoverArtFactory, ReleaseFactory
from users.tests.factories import UserFactory
from amuse.tests.test_mails.country_codes import COUNTRY_CODES, EXPECTED_LOCALIZATION


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class MailLocalizationTestCase(TestCase):
    def assertExpectedTemplateUsed(self, send_func, base_template_name):
        """
        Handle mass testing of email send functionality.

        Provide `send_func` as a function that takes a country code
        which should be used to initiate email sending.

        Django fake mailbox will be inspected for expected templates used.
        """
        self.assertEqual(
            len(COUNTRY_CODES), 250, 'Unexpected amount of country code fixtures'
        )

        for code in COUNTRY_CODES:
            mail.outbox = []

            send_func(code)

            self.assertEqual(len(mail.outbox), 1)

            if code in EXPECTED_LOCALIZATION:
                suffix = EXPECTED_LOCALIZATION[code]
                expected_template_name = f'{base_template_name}_{suffix}'
            else:
                expected_template_name = base_template_name

            self.assertEqual(
                mail.outbox[0].template_name,
                expected_template_name,
                f'Expected template {expected_template_name} '
                f'to be used for country code {code}',
            )

    @responses.activate
    def test_base_template(self):
        add_zendesk_mock_post_response()
        user = UserFactory()

        def send(country):
            user.country = country
            send_base_template(
                'test-sender@example.com', user, 'fake-subject', 'fake-content'
            )

        self.assertExpectedTemplateUsed(send, 'BASE')

    @responses.activate
    def test_password_reset(self):
        add_zendesk_mock_post_response()
        user = UserFactory()

        def send(country):
            user.country = country
            send_password_reset(user)

        self.assertExpectedTemplateUsed(send, 'PASSWORD_RESET')

    @responses.activate
    def test_email_verification(self):
        add_zendesk_mock_post_response()
        user = UserFactory()

        def send(country):
            user.country = country
            send_email_verification(user)

        self.assertExpectedTemplateUsed(send, 'EMAIL_VERIFICATION')

    @responses.activate
    def test_release_pending(self):
        add_zendesk_mock_post_response()
        release = ReleaseFactory()

        def send(country):
            release.user.country = country
            send_release_pending(release)

        self.assertExpectedTemplateUsed(send, 'SUBMISSION_RECEIVED')

    @responses.activate
    def test_release_link(self):
        add_zendesk_mock_post_response()
        release = ReleaseFactory()

        def send(country):
            release.user.country = country
            send_release_link(release)

        self.assertExpectedTemplateUsed(send, 'RELEASE_LINK')

    @responses.activate
    def test_security_update(self):
        add_zendesk_mock_post_response()
        user = UserFactory()

        def send(country):
            user.country = country
            send_security_update_mail(user)

        self.assertExpectedTemplateUsed(send, 'SECURITY_UPDATES')

    @responses.activate
    def test_release_upload_failure(self):
        add_zendesk_mock_post_response()
        release = ReleaseFactory()

        def send(country):
            release.user.country = country
            send_release_upload_failure(release)

        self.assertExpectedTemplateUsed(send, 'SUBMISSION_UPLOAD_FAILURE')
