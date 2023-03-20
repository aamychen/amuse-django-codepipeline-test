import responses
from django.test import override_settings, TestCase
from django.urls import reverse_lazy as reverse
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from users.tests.factories import UserFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class AdminLoginTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.admin = UserFactory(is_staff=True)
        self.user = UserFactory(is_staff=False)

    def test_admin_user_incorrect_password_fails(self):
        url = reverse("admin:login")
        response = self.client.post(
            url, {"username": self.admin.email, "password": "foo1"}
        )
        assert response.status_code == 200

    def test_admin_user_correct_password_successful(self):
        url = reverse("admin:login")
        response = self.client.post(
            url, {"username": self.admin.email, "password": "hunter2"}
        )
        assert response.status_code == 302

    def test_regular_user_incorrect_password_fails(self):
        url = reverse("admin:login")
        response = self.client.post(
            url, {"username": self.user.email, "password": "foo1"}
        )
        assert response.status_code == 200

    def test_regular_user_correct_password_fails(self):
        url = reverse("admin:login")
        response = self.client.post(
            url, {"username": self.user.email, "password": "hunter2"}
        )
        assert response.status_code == 200
