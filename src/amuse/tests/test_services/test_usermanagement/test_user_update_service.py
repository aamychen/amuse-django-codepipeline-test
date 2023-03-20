from unittest import mock

import responses
from django.test import TestCase
from django.urls import reverse_lazy as reverse

from amuse.services.usermanagement import UserUpdateService
from users.models import User
from users.tests.factories import UserFactory


class TestUserSerializerCreate(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory(phone='+123456789')
        self.url = reverse('user-list')

    @responses.activate
    def test_update_user(self):
        data = {
            'first_name': 'Peter',
            'last_name': 'Pan',
            'impact_click_id': 'impact123',
            'appsflyer_id': 'appsflyerid123',
            'email': 'new@email.com',
            'phone': '+388',
            'password': 'new-password',
            'apple_signin_id': 'new-apple-signin-id',
            'google_id': 'new-google-id',
            'facebook_id': 'new-facebook-id',
        }
        user = UserUpdateService().update(instance=self.user, validated_data=data)

        self.assertIsNotNone(user)
        self.assertIsInstance(user, User)

        self.assertEqual(user.first_name, 'Peter')
        self.assertEqual(user.last_name, 'Pan')
        self.assertIsNone(user.apple_signin_id)
        self.assertIsNone(user.google_id)
        self.assertIsNone(user.facebook_id)
        self.assertEqual(user.phone, '+123456789', 'Phone cannot be updated.')
