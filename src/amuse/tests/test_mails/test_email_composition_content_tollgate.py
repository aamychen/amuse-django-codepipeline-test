import responses

from django.core import mail
from django.test import TestCase, override_settings
from amuse.mails import create_localized_template_name
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from amuse.tests.snapshot import snapshot_test
from unittest import mock
from releases.models import Release, Song
from releases.tests.factories import ReleaseFactory, SongFactory
from contenttollgate.mandrill import (
    get_tollgate_templates,
    get_template_by_name,
    get_templates_for_release,
    send_mail,
    send_approved_mail,
    send_not_approved_mail,
    send_rejected_mail,
)
from djrill.exceptions import MandrillRecipientsRefused
from amuse.tests.test_mails.country_codes import COUNTRY_CODES
from users.tests.factories import UserFactory


def create_fake_template(name='Example Template', html=None):
    return {
        'code': html if html else f'<div>HTML in mail {name}</div>',
        'created_at': '2013-01-01 15:30:27',
        'from_email': 'fake-test-sender@example.com',
        'from_name': 'Example Name',
        'labels': [],
        'name': name,
        'publish_code': '<div mc:edit="editable">different than draft content</div>',
        'publish_from_email': 'from.email.published@example.com',
        'publish_from_name': 'Example Published Name',
        'publish_name': 'Example Template',
        'publish_subject': 'example publish_subject',
        'publish_text': 'Example published text',
        'published_at': '2013-01-01 15:30:40',
        'slug': 'example-template',
        'subject': f'Subject of mail {name}',
        'text': 'Example text',
        'updated_at': '2013-01-01 15:30:49',
    }


def create_all_fake_templates(label, lang_labels):
    templates = [
        create_fake_template(
            'INTRO_APPROVED', html='<div>*|RELEASE_NAME|* was approved!!!</div>'
        ),
        create_fake_template(
            'INTRO_APPROVED_ES', html='<div>*|RELEASE_NAME|* hola approvidad!!!</div>'
        ),
        create_fake_template(
            'INTRO_PENDING', html='<div>*|RELEASE_NAME|* is pending...</div>'
        ),
        create_fake_template(
            'INTRO_PENDING_ES', html='<div>*|RELEASE_NAME|* yo tengo pendito...</div>'
        ),
        create_fake_template(
            'INTRO_REJECTED', html='<div>*|RELEASE_NAME|* was REJECTED!</div>'
        ),
        create_fake_template(
            'INTRO_REJECTED_ES', html='<div>*|RELEASE_NAME|* disatro todo!</div>'
        ),
        create_fake_template('SONG-NAME', html='<div>*|SONG_NAME|* has problems</div>'),
        create_fake_template('SONG-NAME_ES', html='<div>*|SONG_NAME|* problemas</div>'),
    ]

    error_names = Release.error_flags.keys() + Song.error_flags.keys()
    for lang_label in lang_labels:
        for error_name in error_names:
            template = create_fake_template()
            template['name'] = f'{lang_label} {error_name}'
            template['labels'] = [label, error_name, lang_label]
            template[
                'code'
            ] = f'''
<div>
    Lorem {label} {lang_label} {error_name}
</div>
'''
            templates.append(template)
    return templates


@responses.activate
@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
def create_release():
    add_zendesk_mock_post_response()
    release = ReleaseFactory(pk=61_928_628, name='My first release')
    release.error_flags.set_bit(2, True)
    release.error_flags.set_bit(7, True)
    song = SongFactory(name='This cool song', release=release, sequence=1)
    song.error_flags.set_bit(0, True)
    song.error_flags.set_bit(7, True)
    song.save()
    return release


def setup_mandrill_mock(mandrill_mock):
    """
    Populate fake API and return fake client.
    """
    fake_templates = create_all_fake_templates('tollgate', ['lang-es', 'lang-en'])

    def return_fake_template(body={}):
        for template in fake_templates:
            if body["name"] == template['name']:
                return template
        raise KeyError(f'Fake mail {name} not defined')

    client_mock = mock.MagicMock()
    client_mock.templates.list = mock.MagicMock(return_value=fake_templates)
    client_mock.templates.info = mock.MagicMock(side_effect=return_fake_template)
    mandrill_mock.return_value = client_mock

    return client_mock


@snapshot_test
@override_settings(MANDRILL_API_KEY='fake-mandrill-key')
@mock.patch('contenttollgate.mandrill.Client')
class MailCompositionContentTollgateTestCase(TestCase):
    def test_get_tollgate_templates(self, mandrill_mock):
        get_tollgate_templates()
        client_mock = mandrill_mock.return_value
        client_mock.templates.list.assert_called_with(body={"label": 'tollgate'})

    def test_get_template_by_name(self, mandrill_mock):
        get_template_by_name('my-template')
        client_mock = mandrill_mock.return_value
        client_mock.templates.info.assert_called_with(body={"name": 'my-template'})

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_get_templates_for_release(self, mandrill_mock):
        """
        Test ensures the templates used for a specific set of
        error flags are used.
        """
        add_zendesk_mock_post_response()
        setup_mandrill_mock(mandrill_mock)

        release = ReleaseFactory()
        release.user.country = 'US'
        release.error_flags.set_bit(2, True)
        release.error_flags.set_bit(7, True)
        result = get_templates_for_release(release)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'lang-en artwork_format')
        self.assertEqual(result[1]['name'], 'lang-en release_date-changed')

        release = ReleaseFactory()
        release.user.country = 'US'

        release.error_flags.set_bit(0, True)
        release.error_flags.set_bit(1, True)
        release.error_flags.set_bit(2, True)
        release.error_flags.set_bit(3, True)
        release.error_flags.set_bit(4, True)
        release.error_flags.set_bit(5, True)
        release.error_flags.set_bit(6, True)
        release.error_flags.set_bit(7, True)
        release.error_flags.set_bit(8, True)
        result = get_templates_for_release(release)
        self.assertEqual(len(result), 9)
        self.assertEqual(result[0]['name'], 'lang-en artwork_social-media')
        self.assertEqual(result[1]['name'], 'lang-en artwork_text')
        self.assertEqual(result[2]['name'], 'lang-en artwork_format')
        self.assertEqual(result[3]['name'], 'lang-en artwork_size')
        self.assertEqual(result[4]['name'], 'lang-en artwork_blurry')
        self.assertEqual(result[5]['name'], 'lang-en explicit_parental-advisory')
        self.assertEqual(result[6]['name'], 'lang-en titles_differs')
        self.assertEqual(result[7]['name'], 'lang-en release_date-changed')
        self.assertEqual(result[8]['name'], 'lang-en release_duplicate')

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_get_templates_for_release_song(self, mandrill_mock):
        """
        Test ensures the templates used for a specific set of
        error flags are used.
        """
        add_zendesk_mock_post_response()

        setup_mandrill_mock(mandrill_mock)

        release = ReleaseFactory()
        release.user.country = 'US'
        song = SongFactory(release=release, sequence=1)
        song.error_flags.set_bit(0, True)
        song.error_flags.set_bit(1, True)
        song.error_flags.set_bit(2, True)
        song.error_flags.set_bit(3, True)
        song.error_flags.set_bit(4, True)
        song.error_flags.set_bit(5, True)
        song.error_flags.set_bit(6, True)
        song.save()

        result = get_templates_for_release(release)
        self.assertEqual(len(result), 8)

        self.assertEqual(result[0]['name'], 'SONG-NAME')
        self.assertEqual(result[1]['name'], 'lang-en rights_samplings')
        self.assertEqual(result[2]['name'], 'lang-en rights_remix')
        self.assertEqual(result[3]['name'], 'lang-en rights_no-rights')
        self.assertEqual(result[4]['name'], 'lang-en audio_bad-quality')
        self.assertEqual(result[5]['name'], 'lang-en explicit_lyrics')
        self.assertEqual(result[6]['name'], 'lang-en genre_not-approved')
        self.assertEqual(result[7]['name'], 'lang-en audio_too-short')

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_get_templates_does_not_get_templates_without_lang_tag(self, mandrill_mock):
        """
        Test ensures no templates without language is returned.
        """
        add_zendesk_mock_post_response()

        fake_templates = create_all_fake_templates('tollgate', ['lang-fr', 'lang-se'])

        client_mock = mock.MagicMock()
        client_mock.templates.list = mock.MagicMock(return_value=fake_templates)
        mandrill_mock.return_value = client_mock

        release = ReleaseFactory()
        release.error_flags.set_bit(2, True)
        release.error_flags.set_bit(7, True)
        result = get_templates_for_release(release)
        self.assertEqual(len(result), 0)

    def test_send_approved_mail(self, mandrill_mock):
        setup_mandrill_mock(mandrill_mock)

        release = create_release()

        for country_code in COUNTRY_CODES:
            release.user.country = country_code

            mail.outbox = []
            send_approved_mail(release)

            template_name = create_localized_template_name(
                'INTRO_APPROVED', country_code
            )

            self.assertEqual(len(mail.outbox), 1)
            sent = mail.outbox[0]
            self.assertEqual(
                sent.template_name, create_localized_template_name('BASE', country_code)
            )
            self.assertEqual(sent.subject, f'Subject of mail {template_name}')
            self.assertEqual(sent.from_email, 'fake-test-sender@example.com')
            self.assertEqual(sent.global_merge_vars['FNAME'], release.user.first_name)
            self.assertEqualSnapshot(
                sent.global_merge_vars['MAIL_CONTENT'].encode('utf-8'),
                f'mail_content-{template_name}.txt',
            )

    def test_send_approved_mail_to_creator_as_well(self, mandrill_mock):
        setup_mandrill_mock(mandrill_mock)

        with mock.patch('amuse.vendor.zendesk.api.create_or_update_user'):
            release = create_release()
            creator = UserFactory()
            release.created_by = creator
            release.save()

        country_code = release.user.country = "SE"

        mail.outbox = []
        send_approved_mail(release)

        template_name = create_localized_template_name('INTRO_APPROVED', country_code)

        self.assertEqual(len(mail.outbox), 2)
        sent = mail.outbox[0]
        self.assertEqual(sent.subject, f'Subject of mail {template_name}')
        self.assertEqual(sent.from_email, 'fake-test-sender@example.com')
        self.assertEqual(sent.global_merge_vars['FNAME'], creator.first_name)
        self.assertEqual(
            mail.outbox[1].global_merge_vars['FNAME'], release.user.first_name
        )
        self.assertEqualSnapshot(
            sent.global_merge_vars['MAIL_CONTENT'].encode('utf-8'),
            f'mail_content-{template_name}.txt',
        )

    def test_dont_send_approved_mail_to_creator_if_same_as_owner(self, mandrill_mock):
        setup_mandrill_mock(mandrill_mock)

        with mock.patch('amuse.vendor.zendesk.api.create_or_update_user'):
            release = create_release()
            creator = UserFactory()
            release.created_by = release.user
            release.save()

        for country_code in COUNTRY_CODES:
            release.user.country = country_code

            mail.outbox = []
            send_approved_mail(release)

            template_name = create_localized_template_name(
                'INTRO_APPROVED', country_code
            )

            self.assertEqual(len(mail.outbox), 1)
            sent = mail.outbox[0]
            self.assertEqual(
                sent.template_name, create_localized_template_name('BASE', country_code)
            )
            self.assertEqual(sent.subject, f'Subject of mail {template_name}')
            self.assertEqual(sent.from_email, 'fake-test-sender@example.com')
            self.assertEqual(sent.global_merge_vars['FNAME'], release.user.first_name)
            self.assertEqualSnapshot(
                sent.global_merge_vars['MAIL_CONTENT'].encode('utf-8'),
                f'mail_content-{template_name}.txt',
            )

    def test_send_approved_mail_handles_no_creator_gracefully(self, mandrill_mock):
        setup_mandrill_mock(mandrill_mock)

        release = create_release()

        for country_code in COUNTRY_CODES:
            release.user.country = country_code

            mail.outbox = []
            send_approved_mail(release)

            template_name = create_localized_template_name(
                'INTRO_APPROVED', country_code
            )

            self.assertEqual(len(mail.outbox), 1)
            sent = mail.outbox[0]
            self.assertEqual(
                sent.template_name, create_localized_template_name('BASE', country_code)
            )
            self.assertEqual(sent.subject, f'Subject of mail {template_name}')
            self.assertEqual(sent.from_email, 'fake-test-sender@example.com')
            self.assertEqual(sent.global_merge_vars['FNAME'], release.user.first_name)
            self.assertEqualSnapshot(
                sent.global_merge_vars['MAIL_CONTENT'].encode('utf-8'),
                f'mail_content-{template_name}.txt',
            )

    def test_send_not_approved_mail(self, mandrill_mock):
        setup_mandrill_mock(mandrill_mock)

        release = create_release()

        for country_code in COUNTRY_CODES:
            release.user.country = country_code

            mail.outbox = []
            send_not_approved_mail(release)

            template_name = create_localized_template_name(
                'INTRO_PENDING', country_code
            )

            self.assertEqual(len(mail.outbox), 1)
            sent = mail.outbox[0]
            self.assertEqual(
                sent.template_name, create_localized_template_name('BASE', country_code)
            )
            self.assertEqual(sent.subject, f'Subject of mail {template_name}')
            self.assertEqual(sent.from_email, 'fake-test-sender@example.com')
            self.assertEqual(sent.global_merge_vars['FNAME'], release.user.first_name)
            self.assertEqualSnapshot(
                sent.global_merge_vars['MAIL_CONTENT'].encode('utf-8'),
                f'mail_content-{template_name}.txt',
            )

    def test_send_rejected_mail(self, mandrill_mock):
        setup_mandrill_mock(mandrill_mock)

        release = create_release()

        for country_code in COUNTRY_CODES:
            release.user.country = country_code

            mail.outbox = []
            send_rejected_mail(release)

            template_name = create_localized_template_name(
                'INTRO_REJECTED', country_code
            )

            self.assertEqual(len(mail.outbox), 1)
            sent = mail.outbox[0]
            self.assertEqual(
                sent.template_name, create_localized_template_name('BASE', country_code)
            )
            self.assertEqual(sent.subject, f'Subject of mail {template_name}')
            self.assertEqual(sent.from_email, 'fake-test-sender@example.com')
            self.assertEqual(sent.global_merge_vars['FNAME'], release.user.first_name)
            self.assertEqualSnapshot(
                sent.global_merge_vars['MAIL_CONTENT'].encode('utf-8'),
                f'mail_content-{template_name}.txt',
            )

    def test_send_mail_exception_raised(self, mandrill_mock):
        send_base_template_mock = mock.Mock(side_effect=MandrillRecipientsRefused())
        with self.assertRaises(MandrillRecipientsRefused) as exception_raised:
            with mock.patch(
                'contenttollgate.mandrill.send_base_template', send_base_template_mock
            ) as context:
                with mock.patch(
                    'contenttollgate.mandrill.logger.warning'
                ) as mocked_logger:
                    send_mail(None, None, None)
                assert mocked_logger.call_count() == 1

    @responses.activate
    @override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
    def test_only_send_not_approved_mail_for_appropriate_flags(self, mandrill_mock):
        add_zendesk_mock_post_response()

        setup_mandrill_mock(mandrill_mock)
        release = ReleaseFactory()
        song = SongFactory(release=release)

        # Mail should not be sent when there are no error flags
        mail.outbox = []
        send_not_approved_mail(release)
        self.assertEqual(0, len(mail.outbox))

        # Mail should not be sent for these error flags
        explicit_parental_advisory_flag = 5
        release_date_changed_flag = 7
        release.error_flags.set_bit(explicit_parental_advisory_flag, True)
        release.error_flags.set_bit(release_date_changed_flag, True)
        release.save()

        explicit_lyrics_flag = 4
        song.error_flags.set_bit(explicit_lyrics_flag, True)
        song.save()

        mail.outbox = []
        send_not_approved_mail(release)
        self.assertEqual(0, len(mail.outbox))

        # Send mail for any other flag on release
        release.error_flags.set_bit(3, True)
        release.save()

        mail.outbox = []
        send_not_approved_mail(release)
        self.assertEqual(1, len(mail.outbox))

        release.error_flags.set_bit(3, False)
        release.save()

        # Send mail for any other flag on song
        song.error_flags.set_bit(1, True)
        song.save()

        mail.outbox = []
        send_not_approved_mail(release)
        self.assertEqual(1, len(mail.outbox))
