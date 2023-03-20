from django.test import TestCase

from amuse.view_log_base import ViewLogBase


class ViewLogBaseTestCase(TestCase):
    def test_purchase_token_is_not_filtered(self):
        data = {
            'purchase_token': '123',
            'other_token': '456',
            'item': {'purchase_token': '789', 'password': 'abc', 'name': 'John'},
        }

        actual = ViewLogBase().clean_data(data)

        expected = {
            'purchase_token': '123',
            'other_token': ViewLogBase.FILTERED_PLACEHOLDER,
            'item': {
                'purchase_token': '789',
                'password': ViewLogBase.FILTERED_PLACEHOLDER,
                'name': 'John',
            },
        }
        self.assertEqual(expected, actual)
