from django.test import TestCase

from amuse.api.v4.serializers.invite import InviteSerializer


class TestInviteSerializer(TestCase):
    def setUp(self):
        self.data = {
            'name': 'Artist full name',
            'email': 'artist@example.com',
            'phone_number': '+46723345678',
        }

    def test_create_serializer(self):
        serializer = InviteSerializer(data=self.data)

        self.assertTrue(serializer.is_valid())

    def test_data_without_email_is_valid(self):
        self.data['email'] = None
        serializer = InviteSerializer(data=self.data)

        self.assertTrue(serializer.is_valid())

    def test_data_without_phone_number_is_valid(self):
        self.data['phone_number'] = None
        serializer = InviteSerializer(data=self.data)

        self.assertTrue(serializer.is_valid())

    def test_data_without_phone_number_and_email_is_invalid(self):
        self.data['email'] = None
        self.data['phone_number'] = None
        serializer = InviteSerializer(data=self.data)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors.keys()), {'non_field_errors'})

        expected_error_message = 'Both email and phone_number are empty'
        returned_error_message = str(serializer.errors['non_field_errors'][0])

        self.assertEqual(returned_error_message, expected_error_message)

    def test_invalid_phone_number_raises_validation_error(self):
        self.data['phone_number'] = 'invalid_phone_number'
        serializer = InviteSerializer(data=self.data)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors.keys()), {'phone_number'})

        expected_error_message = 'Enter a valid phone number.'
        returned_error_message = str(serializer.errors['phone_number'][0])

        self.assertEqual(returned_error_message, expected_error_message)

    def test_wrong_phone_number_raises_validation_error(self):
        self.data['phone_number'] = '+460000000000'
        serializer = InviteSerializer(data=self.data)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors.keys()), {'phone_number'})

        expected_error_message = 'Enter a valid phone number.'
        returned_error_message = str(serializer.errors['phone_number'][0])

        self.assertEqual(returned_error_message, expected_error_message)

    def test_invalid_email_raises_validation_error(self):
        self.data['email'] = 'invalid_email'
        serializer = InviteSerializer(data=self.data)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors.keys()), {'email'})

        expected_error_message = 'Enter a valid email address.'
        returned_error_message = str(serializer.errors['email'][0])

        self.assertEqual(returned_error_message, expected_error_message)

    def test_validated_data_keys(self):
        serializer = InviteSerializer(data=self.data)
        serializer.is_valid()
        self.assertEqual(set(serializer.validated_data.keys()), set(self.data.keys()))

    def test_validated_data_field_values(self):
        serializer = InviteSerializer(data=self.data)
        serializer.is_valid()
        self.assertEqual(serializer.validated_data['name'], self.data['name'])
        self.assertEqual(serializer.validated_data['email'], self.data['email'])
        self.assertEqual(
            serializer.validated_data['phone_number'], self.data['phone_number']
        )
