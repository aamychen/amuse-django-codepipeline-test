from unittest.mock import Mock

from django.test import TestCase

from amuse.api.v4.serializers.genre import GenreSerializer
from releases.tests.factories import GenreFactory


class TestGenreSerializer(TestCase):
    def test_genre_serializer_data(self):
        mocked_request = Mock()

        data = {'id': 1, 'name': 'Genre'}
        serializer = GenreSerializer(data=data, context={'request': mocked_request})

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['id'], data['id'])
        self.assertEqual(serializer.validated_data['name'], data['name'])
