from django.urls import reverse
from rest_framework import status

from releases.tests.factories import MetadataLanguageFactory
from amuse.tests.test_api.base import AmuseAPITestCase


class MetadataLanguageAPITestCase(AmuseAPITestCase):
    def setUp(self):
        super().setUp()

        generic_lang = MetadataLanguageFactory(
            name='Swedish', fuga_code='se', iso_639_1='se', sort_order=1
        )
        none_lang = MetadataLanguageFactory(
            name='Creole, French based',
            fuga_code='cpf',
            iso_639_1='fr',
            is_title_language=False,
            is_lyrics_language=False,
        )
        title_lang = MetadataLanguageFactory(
            name='Chinese, Mandarin Traditional ',
            fuga_code='cmn_hant',
            iso_639_1='cm',
            is_lyrics_language=False,
            sort_order=2,
        )
        lyrics_lang = MetadataLanguageFactory(
            name='Instrumental',
            fuga_code='zxx',
            iso_639_1='zx',
            is_title_language=False,
            sort_order=3,
        )

        self.languages = [generic_lang, title_lang, lyrics_lang, none_lang]

    def test_list(self):
        url = reverse('metadata-languages-list')
        expected_response_keys = [
            'iso_639_1',
            'sort_order',
            'is_title_language',
            'is_lyrics_language',
            'fuga_code',
            'name',
        ]

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)
        self.assertEqual(
            sorted(list(response.data[0].keys())), sorted(expected_response_keys)
        )

    def test_data_sorting_correct(self):
        url = reverse('metadata-languages-list')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(response.data))
        for index, language in enumerate(response.data):
            self.assertEqual(language['sort_order'], self.languages[index].sort_order)

    def test_data_availability_correct(self):
        url = reverse('metadata-languages-list')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(response.data))
        for index, language in enumerate(response.data):
            self.assertEqual(
                language['is_title_language'], self.languages[index].is_title_language
            )
            self.assertEqual(
                language['is_lyrics_language'], self.languages[index].is_lyrics_language
            )
