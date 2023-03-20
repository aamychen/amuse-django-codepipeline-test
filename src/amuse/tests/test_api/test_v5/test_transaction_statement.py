import json
from decimal import Decimal
from unittest import mock
from uuid import uuid4

import responses
from django.conf import settings
from django.urls import reverse_lazy as reverse
from flaky import flaky
from rest_framework import status
from waffle.models import Flag, Switch

from amuse.api.v4.serializers.transaction import (
    MAINTENANCE_MESSAGE,
    VERIFY_EMAIL_MESSAGE,
)
from amuse.tests.helpers import (
    hyperwallet_mock_response_create_payment,
    hyperwallet_mock_response_create_user,
    hyperwallet_mock_response_error,
    mock_update_offer,
    mock_validate_offer,
)
from amuse.tests.test_api.base import API_V4_ACCEPT_VALUE, AmuseAPITestCase
from users.tests.factories import UserFactory


class TransactionAPIV4TestCase(AmuseAPITestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.url = reverse("user-transactions", kwargs={"user_id": self.user.pk})

    # mock out PubSub
    @mock.patch("amuse.vendor.gcp.pubsub.PubSubClient.publish")
    @mock.patch("amuse.vendor.gcp.pubsub.PubSubClient.authenticate")
    def test_post_statement_request_succesfull(self, mocked_publish, mocked_auth):
        self.client.credentials(HTTP_ACCEPT='application/json; version=5')
        response = self.client.post(
            reverse("user-transactions-statement", kwargs={"user_id": self.user.pk}),
            json.dumps({"start_date": "2021-01-01", "end_date": "2021-10-01"}),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['is_success'] == True

    def test_post_statement_request_bad_request(self):
        self.client.credentials(HTTP_ACCEPT='application/json; version=5')
        response = self.client.post(
            reverse("user-transactions-statement", kwargs={"user_id": self.user.pk}),
            {"start_date": "2021-01-01"},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
