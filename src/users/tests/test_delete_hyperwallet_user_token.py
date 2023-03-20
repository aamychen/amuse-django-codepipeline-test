import responses

from django.test import override_settings

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from amuse.tests.test_api.base import AmuseAPITestCase
from users.models import UserMetadata
from users.tests.factories import UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class DeleteHyperwalletUserTokenTestCase(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory()
        self.usermetadata = UserMetadata(user=self.user, hyperwallet_user_token='xxx')
        self.usermetadata.save()

        self.admin = UserFactory(is_staff=True)

        self.client.force_login(self.admin)

    def test_post_deletes_hyperwallet_user_token(self):
        url = '/admin/users/user/%s/delete-hyperwallet-user-token/' % self.user.pk
        payload = {'object_id': self.user.pk, 'confirm': 'yes'}

        response = self.client.post(url, payload)
        assert response.status_code == 302

        self.usermetadata.refresh_from_db()
        assert self.usermetadata.hyperwallet_user_token is None

    def test_no_usermetadata_returns_error(self):
        url = '/admin/users/user/%s/delete-hyperwallet-user-token/' % self.user.pk
        payload = {'object_id': self.user.pk, 'confirm': 'yes'}

        UserMetadata.objects.all().delete()

        response = self.client.post(url, payload)
        assert response.status_code == 500
