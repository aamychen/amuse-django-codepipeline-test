from django.test import TestCase

from codes.tests.factories import MetadataLanguageFactory
from releases.models import MetadataLanguage


class MetadataLanguageTestCase(TestCase):
    def test_find_language_by_fuga_code(self):
        expected = MetadataLanguageFactory(fuga_code='zz', iso_639_1='xx')

        by_iso_code = MetadataLanguage.by_code(expected.iso_639_1)

        self.assertIsNone(by_iso_code)

        by_fuga_code = MetadataLanguage.by_code(expected.fuga_code)

        self.assertEqual(by_fuga_code.iso_639_1, expected.iso_639_1)
        self.assertEqual(by_fuga_code.fuga_code, expected.fuga_code)

    def test_finding_language_by_invalid_code_will_return_none(self):
        MetadataLanguageFactory(fuga_code='zz', iso_639_1='xx')

        no_match = MetadataLanguage.by_code('invalid')
        self.assertIsNone(no_match)

    def test_default_manager_only_includes_fuga_languages(self):
        [MetadataLanguageFactory(fuga_code=None) for i in range(10)]

        ml = MetadataLanguageFactory(fuga_code='AM')

        assert MetadataLanguage.objects.count() == 1
        assert list(MetadataLanguage.objects.all()) == [ml]

    def test_languages_get_default_sort_order_if_one_is_not_specified(self):
        ml = MetadataLanguage.objects.create(
            name='NAME', fuga_code='AM', iso_639_1='US'
        )

        assert ml.sort_order == MetadataLanguage.DEFAULT_SORT_ORDER

    def test_sort_order_based_on_the_sort_order_field(self):
        [MetadataLanguageFactory(sort_order=i) for i in reversed(range(1, 10, 2))]

        previous = 0

        for language in MetadataLanguage.objects.all():
            assert language.sort_order > previous
            previous = language.sort_order

    def test_sorting_done_on_name_if_same_sort_order_value(self):
        for lang in [(2, 'XXX'), (2, 'BBB'), (1, 'AAA'), (1, 'ZZZ')]:
            MetadataLanguageFactory(
                sort_order=lang[0], name=lang[1], fuga_code=lang[1][:2]
            )

        expected_order = ['AAA', 'ZZZ', 'BBB', 'XXX']

        for language in MetadataLanguage.objects.all():
            assert language.name == expected_order.pop(0)
