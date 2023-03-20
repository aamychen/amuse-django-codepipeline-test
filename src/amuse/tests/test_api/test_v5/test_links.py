from unittest.mock import patch

from django.urls import reverse

from amuse.tests.test_api.base import AmuseAPITestCase
from users.tests.factories import UserFactory
from amuse.models.link import Link


class LinkViewTestCase(AmuseAPITestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, mock_zendesk):
        super().setUp()
        self.url = reverse('links')
        self.user = UserFactory()
        self.client.force_authenticate(self.user)
        self.client.credentials()

    def test_logged_out_user(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_get_empty_links(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.json(), {'data': {}})

    def test_get_links(self):
        # Test setup
        staging_link = Link(name='staging_url', link='https://api-staging.amuse.io/')
        staging_link.save()
        production_link = Link(name='production_url', link='https://api.amuse.io/')
        production_link.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(
            response.json(),
            {
                'data': {
                    'staging_url': 'https://api-staging.amuse.io/',
                    'production_url': 'https://api.amuse.io/',
                }
            },
        )
