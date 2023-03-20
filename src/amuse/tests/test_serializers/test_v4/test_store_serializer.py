from django.test import TestCase

from amuse.api.v4.serializers.store import StoreSerializer
from releases.tests.factories import StoreFactory, StoreCategoryFactory


class TestStoreSerializer(TestCase):
    def setUp(self):
        self.store = {
            'id': 1,
            'name': 'Test Store',
            'slug': 'test_store123',
            'logo': 'https://amuse.io/',
            'logo_color': None,
            'category': {'name': 'test'},
            'org_id': 'test_org',
            'order': 123,
            'active': True,
            'admin_active': True,
            'is_pro': False,
            'category_id': None,
            'parent_id': None,
            'extra_info': None,
        }

    def test_serialize(self):
        category = StoreCategoryFactory()
        store = StoreFactory(category=category)

        serialized = StoreSerializer(store).data

        self.assertEqual(serialized['id'], store.pk)
        self.assertEqual(serialized['is_pro'], store.is_pro)
        self.assertEqual(serialized['name'], store.name)
        self.assertEqual(serialized['order'], store.order)
        self.assertEqual(serialized['category']['name'], category.name)
        self.assertEqual(serialized['category']['order'], category.order)

    def test_hex_color_short(self):
        self.store['hex_color'] = "#FFF"
        assert StoreSerializer(data=self.store).is_valid() is True

    def test_hex_color_long(self):
        self.store['hex_color'] = "#ffFFff"
        assert StoreSerializer(data=self.store).is_valid() is True

    def test_hex_color_alpha(self):
        self.store['hex_color'] = "#fF000055"
        assert StoreSerializer(data=self.store).is_valid() is True

    def test_hex_color_non_hex(self):
        self.store['hex_color'] = "asdf"
        assert StoreSerializer(data=self.store).is_valid() is False

    def test_hex_color_incomplete(self):
        self.store['hex_color'] = "#FFFFF"
        assert StoreSerializer(data=self.store).is_valid() is False

    def test_slug_underscore(self):
        self.store['slug'] = "TEST_stOre_123"
        assert StoreSerializer(data=self.store).is_valid() is True

    def test_slug_hyphen(self):
        self.store['slug'] = "tesT-stOre-123"
        assert StoreSerializer(data=self.store).is_valid() is True

    def test_slug_whitespace(self):
        self.store['slug'] = "test store 123"
        assert StoreSerializer(data=self.store).is_valid() is False

    def test_slug_dots(self):
        self.store['slug'] = "test.store.123"
        assert StoreSerializer(data=self.store).is_valid() is False
