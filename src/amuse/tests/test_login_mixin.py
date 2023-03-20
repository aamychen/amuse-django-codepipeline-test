from uuid import uuid4
import responses
from rest_framework import status
from django.test import TestCase, RequestFactory
from amuse.tests.test_api.base import AmuseAPITestCase
from rest_framework.response import Response
from users.tests.factories import UserFactory
from amuse.tests.helpers import add_zendesk_mock_post_response
from amuse.mixins import LogMixin


class MockQueryParams:
    def dict(self):
        return {"a": 1}


class TestLogMixin(AmuseAPITestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory(
            country="US",
            email='test@example.com',
            phone='+524423439277',
            phone_verified=True,
        )
        self.request = RequestFactory().post('/test/request/')
        self.response_data = {
            "errors": [
                {
                    "message": "Error messaage",
                    "fieldName": "clientUserId",
                    "code": "ERROR_CODE",
                    "relatedResources": ["usr-3c0840da-fbf4-464d-9bcb-a16018de66b7"],
                }
            ]
        }
        self.request.user = self.user
        self.request.query_params = MockQueryParams()
        self.request.data = {
            "profile_type": "INDIVIDUAL",
            "dob": "1980-01-01",
            "address": "123 Main Street",
            "city": "New York",
            "state_province": "NY",
            "postal_code": "10016",
        }
        self.request.request_id = uuid4()
        self.response = Response(
            data=self.response_data, status=status.HTTP_400_BAD_REQUEST
        )
        self.mixin = LogMixin()
        setattr(self.mixin, 'request', self.request)

    def test_log_mixin(self):
        response, log_data = self.mixin.finalize_response(
            request=self.request, response=self.response, test=True
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(log_data["request"], str)
        self.assertIsInstance(log_data["response"], str)
        self.assertIsInstance(log_data["headers"], str)
        self.assertIsInstance(log_data['query_params'], str)
