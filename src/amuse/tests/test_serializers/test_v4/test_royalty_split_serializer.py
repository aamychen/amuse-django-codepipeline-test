from django.test import TestCase, override_settings
import responses

from amuse.api.v4.serializers.royalty_split import RoyaltySplitSerializer
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from users.tests.factories import UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class TestRoyaltySplitSerializer(TestCase):
    @responses.activate
    def setUp(self) -> None:
        add_zendesk_mock_post_response()

        user = UserFactory()
        invite = {
            'name': 'Artist Name',
            'email': 'artist@example.com',
            'phone_number': '+46723345678',
        }
        self.data = {'user_id': user.id, 'rate': 1.0, 'invite': invite}

    def test_create_serializer(self):
        serializer = RoyaltySplitSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())

    def test_rate_less_or_equal_one(self):
        self.data['rate'] = 1.1
        serializer = RoyaltySplitSerializer(data=self.data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors.keys()), {'rate'})

    def test_rate_positive(self):
        self.data['rate'] = 0.0
        serializer = RoyaltySplitSerializer(data=self.data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors.keys()), {'rate'})

    def test_validated_data_keys(self):
        serializer = RoyaltySplitSerializer(data=self.data)
        serializer.is_valid()
        self.assertEqual(set(serializer.validated_data.keys()), set(self.data.keys()))

    def test_validated_data_field_values(self):
        serializer = RoyaltySplitSerializer(data=self.data)
        serializer.is_valid()
        self.assertEqual(serializer.validated_data['rate'], self.data['rate'])
        self.assertEqual(serializer.validated_data['user_id'], self.data['user_id'])
        self.assertEqual(serializer.validated_data['invite'], self.data['invite'])

    def test_data_without_invite_is_valid(self):
        self.data['invite'] = None
        serializer = RoyaltySplitSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())

    def test_data_without_user_id_is_valid(self):
        self.data['user_id'] = None
        serializer = RoyaltySplitSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())

    def test_data_with_user_id_does_not_exist_is_invalid(self):
        self.data['user_id'] = 1237685123
        serializer = RoyaltySplitSerializer(data=self.data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors.keys()), {'non_field_errors'})
        expected_error_message = 'User does not exist'
        returned_error_message = str(serializer.errors['non_field_errors'][0])
        self.assertEqual(returned_error_message, expected_error_message)

    def test_data_without_user_id_and_invite_is_invalid(self):
        self.data['invite'] = None
        self.data['user_id'] = None
        serializer = RoyaltySplitSerializer(data=self.data)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors.keys()), {'non_field_errors'})

        expected_error_message = 'Both user_id and invite are empty.'
        returned_error_message = str(serializer.errors['non_field_errors'][0])

        self.assertEqual(returned_error_message, expected_error_message)
