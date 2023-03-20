import json
from unittest import mock

import responses
from django.urls import reverse_lazy as reverse
from rest_framework import status

from amuse.tests.test_api.base import API_V4_ACCEPT_VALUE, AmuseAPITestCase
from amuse.tests.test_vendor.test_revenue.helpers import (
    mock_wallet,
    mock_wallet_month_filter,
)
from amuse.vendor.revenue.client import URL_WALLET
from users.tests.factories import UserFactory


class TransactionAPIV4TestCase(AmuseAPITestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.url = reverse("user-transactions", kwargs={"user_id": self.user.pk})

    @responses.activate
    def test_get_wallet(self):
        responses.add(responses.GET, URL_WALLET % self.user.pk, mock_wallet, status=200)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == json.loads(mock_wallet)

    @responses.activate
    def test_get_wallet_handles_not_implemented(self):
        self.client.credentials(HTTP_ACCEPT='application/json; version=X')
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @responses.activate
    def test_get_wallet_with_month_filter(self):
        self.url = reverse(
            "user-transactions",
            kwargs={"user_id": self.user.pk, "year_month": "2020-01"},
        )
        responses.add(
            responses.GET,
            (URL_WALLET % self.user.pk) + "?month=2020-01",
            mock_wallet_month_filter,
            status=200,
        )
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == json.loads(mock_wallet_month_filter)

    @responses.activate
    def test_get_wallet_handles_errors(self):
        responses.add(responses.GET, URL_WALLET % self.user.pk, status=500)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data is None

    @responses.activate
    @mock.patch("amuse.vendor.revenue.client.requests.get")
    def test_get_wallet_handles_exceptions(self, mocked_get):
        mocked_get.side_effect = ConnectionError
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data is None


class TransactionAPIV4Blocked(AmuseAPITestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.url = reverse("user-withdrawal")

    def test_post_returns_400(self):
        response = self.client.post(self.url, data={})
        assert response.status_code == 400
        assert response.json()['detail'] == "Withdrawal method not supported"
