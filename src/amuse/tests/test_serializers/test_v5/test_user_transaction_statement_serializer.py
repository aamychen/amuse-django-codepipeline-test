from unittest import mock
from django.test import TestCase, RequestFactory
from users.tests.factories import UserFactory
from amuse.api.v5.serializers.transactions_statement import (
    CreateStatementRequestSerializer,
)


class TestCreateStatementRequestSerializer(TestCase):
    @mock.patch("amuse.vendor.gcp.pubsub.PubSubClient.publish")
    @mock.patch("amuse.vendor.gcp.pubsub.PubSubClient.authenticate")
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def test_update_payee_serializer_failed_event_write(
        self, mocked_zendesk, mock_gcp_auth, mock_pubsub
    ):
        user = UserFactory(
            country="US",
            email='a392c814@example.com',
            phone='+444423439277',
            phone_verified=True,
        )
        to_serializer = {
            "file_format": "xlsx",
            "start_date": "2021-01-01",
            "end_date": "2021-10-01",
        }
        request = RequestFactory().post(f'users/{user.id}/transactions/statement/')
        request.user = user
        context = {'request': request}
        serializer = CreateStatementRequestSerializer(data=to_serializer)
        serializer.context['request'] = request
        self.assertTrue(serializer.is_valid())
        data = serializer.request_statement()
        self.assertTrue(data['is_success'])
