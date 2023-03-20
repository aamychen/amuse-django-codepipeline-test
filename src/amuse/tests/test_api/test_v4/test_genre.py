from django.db import connection, reset_queries
from django.urls import reverse_lazy as reverse
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from releases.models import Genre
from releases.tests.factories import GenreFactory

from ..base import AmuseAPITestCase


class GenreAPITestCase(AmuseAPITestCase):
    def test_list(self):
        url = reverse('genre-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        genre1 = GenreFactory()
        genre2 = GenreFactory(parent=genre1)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        root_genre = response.data[0]
        # Make sure the top level structure is correct
        self.assertCountEqual(root_genre.keys(), ['id', 'name', 'subgenres'])
        self.assertEqual(root_genre['id'], genre1.id)
        self.assertEqual(root_genre['name'], genre1.name)
        self.assertEqual(len(root_genre['subgenres']), 1)
        # Ensure the subgenre structure is also correct
        subgenre = root_genre['subgenres'][0]
        self.assertCountEqual(subgenre.keys(), ['id', 'name'])
        self.assertEqual(subgenre['id'], genre2.id)
        self.assertEqual(subgenre['name'], genre2.name)

    def test_status(self):
        genre1 = GenreFactory()
        GenreFactory(parent=genre1)
        GenreFactory(parent=genre1, status=Genre.STATUS_INACTIVE)

        url = reverse('genre-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(len(response.data[0]['subgenres']), 1)

    def test_filter_on_yt_content_id(self):
        electronic_parent = GenreFactory(name='Electronic')
        other_parent = GenreFactory()
        g1 = GenreFactory(parent=electronic_parent)
        g2 = GenreFactory(parent=electronic_parent)
        g3 = GenreFactory(parent=other_parent)
        g4 = GenreFactory(parent=other_parent)

        # With yt content id not allowed
        url = reverse('genre-list')
        response = self.client.get(url, {'yt_content_id': 'exclude'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual(2, len(response.data[0]['subgenres']))

        names = {g['name'] for g in response.data[0]['subgenres']}
        self.assertEqual({g1.name, g2.name}, names)

        # With yt content id allowed
        url = reverse('genre-list')
        response = self.client.get(url, {'yt_content_id': 'only'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertEqual(2, len(response.data[0]['subgenres']))

        names = {g['name'] for g in response.data[0]['subgenres']}
        self.assertEqual({g3.name, g4.name}, names)


class GenreAPIDBCallsTestCase(APITransactionTestCase):
    @override_settings(DEBUG=True)
    def test_number_of_db_calls(self):
        genre1 = GenreFactory()

        GenreFactory(parent=genre1)
        GenreFactory(parent=genre1, status=Genre.STATUS_INACTIVE)

        GenreFactory(parent=GenreFactory())
        GenreFactory(parent=GenreFactory())

        reset_queries()

        with self.assertNumQueries(2):
            response = self.client.get(reverse("genre-list"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 3)
        assert len(connection.queries) == 2
