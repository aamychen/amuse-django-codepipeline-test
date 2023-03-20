from django.conf import settings
from django.test import TestCase

from amuse.mails import resolve_lang, create_localized_template_name


class MailTemplateLocalizationTestCase(TestCase):
    def test_resolve_lang_fallback(self):
        fake_country_code = '_XYZ'
        self.assertEqual(resolve_lang(fake_country_code), None)

    def test_resolve_lang_for_xx(self):
        self.assertEqual(resolve_lang('XX'), 'ES')

    def test_fallback_to_no_suffix(self):
        template_name = create_localized_template_name('FAKE_TEMPLATE_NAME', 'US')
        self.assertEqual(template_name, 'FAKE_TEMPLATE_NAME')

    def test_suffix_for_fake_country(self):
        template_name = create_localized_template_name('FAKE_TEMPLATE_NAME', 'XX')
        self.assertEqual(template_name, 'FAKE_TEMPLATE_NAME_ES')
