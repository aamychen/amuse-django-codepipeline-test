from django.urls import reverse_lazy as reverse
from rest_framework.test import APITransactionTestCase
from django.db import connection, reset_queries
from django.test import override_settings
from rest_framework import status

from amuse.tests.test_api.base import (
    API_V2_ACCEPT_VALUE,
    API_V4_ACCEPT_VALUE,
    AmuseAPITestCase,
)
from releases.tests.factories import StoreFactory, StoreCategoryFactory
from users.models import UserArtistRole
from users.tests.factories import UserFactory, UserArtistRoleFactory, Artistv2Factory


class StoreAPITestCase(AmuseAPITestCase):
    def setUp(self):
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.user = UserFactory()
        self.url = reverse('store-list')

    def test_list(self):
        StoreFactory()
        StoreFactory()
        StoreFactory()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_format(self):
        StoreFactory()

        response = self.client.get(self.url)

        self.assertEqual(
            sorted(list(response.data[0].keys())),
            [
                'active',
                'admin_active',
                'batch_size',
                'category',
                'extra_info',
                'fuga_store',
                'hex_color',
                'id',
                'internal_name',
                'is_pro',
                'logo',
                'logo_color',
                'multi_batch_support',
                'name',
                'order',
                'org_id',
                'parent',
                'show_on_top',
                'slug',
            ],
        )

    def test_all_stores_visible(self):
        StoreFactory(name="Foo")
        StoreFactory(name="Bar", active=False)
        StoreFactory(name="Baz")

        response = self.client.get(self.url)

        self.assertEqual(len(response.data), 3)

    def test_inactive_stores_marked_as_inactive(self):
        StoreFactory(active=False)

        response = self.client.get(self.url)
        self.assertEqual(response.data[0]['active'], False)

    def test_active_stores_marked_as_active(self):
        StoreFactory(active=True)

        response = self.client.get(self.url)
        self.assertEqual(response.data[0]['active'], True)

    def test_admin_active_stores_marked_as_active(self):
        StoreFactory(active=False, admin_active=True)

        response = self.client.get(self.url)
        self.assertEqual(response.data[0]['active'], False)
        self.assertEqual(response.data[0]['admin_active'], True)

    def test_admin_inactive_stores_marked_as_inactive(self):
        StoreFactory(active=True, admin_active=False)

        response = self.client.get(self.url)
        self.assertEqual(response.data[0]['active'], True)
        self.assertEqual(response.data[0]['admin_active'], False)

    def test_free_stores_marked_as_not_is_pro(self):
        StoreFactory(is_pro=False)

        response = self.client.get(self.url)
        self.assertEqual(response.data[0]['is_pro'], False)

    def test_pro_stores_marked_as_is_pro(self):
        StoreFactory(is_pro=True)

        response = self.client.get(self.url)
        self.assertEqual(response.data[0]['is_pro'], True)

    def test_pro_stores_in_response(self):
        StoreFactory(is_pro=True)
        StoreFactory(is_pro=False)

        response = self.client.get(self.url)
        self.assertEqual(len(response.data), 2)

    def test_unsupported_api_version_raises_error(self):
        self.client.credentials(HTTP_ACCEPT=API_V2_ACCEPT_VALUE)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parent_store_returned_as_id_in_response(self):
        parent = StoreFactory()
        child = StoreFactory(parent=parent)

        response = self.client.get(self.url)
        child_data = list(filter(lambda s: s['parent'] == parent.pk, response.data))[0]

        assert child_data['id'] == child.pk

    def test_audiomack_store_not_returned_for_unauthenticated_user(self):
        StoreFactory(name='Deezer', active=True, internal_name='deezer')
        StoreFactory(name='Audiomack', active=True, internal_name='audiomack')

        response = self.client.get(self.url)

        for store in response.data:
            self.assertNotIn(store['name'], 'Audiomack')

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Deezer')

    def test_audiomack_store_returned_for_authetnitcated_user(self):
        artist = self.user.create_artist_v2(name='Mad Skillz', audiomack_id='123')
        self.client.force_authenticate(self.user)

        StoreFactory(name='Deezer', active=True, internal_name='deezer')
        StoreFactory(name='Audiomack', active=True, internal_name='audiomack')

        response = self.client.get(self.url, data={"artist_id": artist.id})

        self.assertEqual(len(response.data), 2)
        for store in response.data:
            self.assertIn(store['name'], {'Audiomack', 'Deezer'})

    def test_audiomack_store_not_returned_without_artist_param_or_main_artist(self):
        artist = self.user.create_artist_v2(name='Mad Skillz', audiomack_id='123')
        self.client.force_authenticate(self.user)

        StoreFactory(name='Deezer', active=True, internal_name='deezer')
        StoreFactory(name='Audiomack', active=True, internal_name='audiomack')

        response = self.client.get(self.url)

        for store in response.data:
            self.assertNotIn(store['name'], 'Audiomack')

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Deezer')

    def test_audiomack_store_not_returned_for_authenticated_spectator(self):
        artist = Artistv2Factory(name='Mad Skillz', audiomack_id='123')
        UserArtistRoleFactory(
            user=self.user, artist=artist, type=UserArtistRole.SPECTATOR
        )
        self.client.force_authenticate(self.user)

        StoreFactory(name='Deezer', active=True, internal_name='deezer')
        StoreFactory(name='Audiomack', active=True, internal_name='audiomack')

        response = self.client.get(self.url, data={"artist_id": artist.id})

        for store in response.data:
            self.assertNotIn(store['name'], 'Audiomack')

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Deezer')

    def test_audiomack_store_not_returned_for_non_existent_artist(self):
        self.client.force_authenticate(self.user)

        StoreFactory(name='Deezer', active=True, internal_name='deezer')
        StoreFactory(name='Audiomack', active=True, internal_name='audiomack')

        response = self.client.get(self.url, data={'artist_id': '123456'})

        for store in response.data:
            self.assertNotIn(store['name'], 'Audiomack')

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Deezer')


class StoreAPIDBCallsTestCase(APITransactionTestCase):
    def setUp(self):
        self.user = UserFactory()
        self.url = reverse('store-list')
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)

    @override_settings(DEBUG=True)
    def test_number_of_db_calls(self):
        StoreFactory(category=StoreCategoryFactory())
        StoreFactory(category=StoreCategoryFactory())
        StoreFactory(category=StoreCategoryFactory())

        reset_queries()

        with self.assertNumQueries(1):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 3)
        assert len(connection.queries) == 1
