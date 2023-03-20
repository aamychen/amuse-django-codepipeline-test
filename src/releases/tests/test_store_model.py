from django.test import TestCase

from releases.models import Store
from releases.tests.factories import StoreFactory


class StoreTestCase(TestCase):
    def test_inactive_store_not_in_active(self):
        active_store = StoreFactory()
        inactive_store = StoreFactory(active=False)

        stores = Store.objects.active()

        self.assertCountEqual([active_store], stores)

    def test_from_internal_name(self):
        audiomack = StoreFactory(name='Audiomack', internal_name='audiomack')
        spotify = StoreFactory(name='Spotify', internal_name='spotify')

        self.assertEqual(audiomack, Store.from_internal_name('audiomack'))
        self.assertEqual(spotify, Store.from_internal_name('spotify'))
        self.assertIsNone(Store.from_internal_name('store-not-exists'))
