from django.test import TestCase
from rest_framework.serializers import ValidationError

from amuse.services.usermanagement.signup_flows.signup_flow_factory import RegularFlow


class TestRegularFlowCase(TestCase):
    def test_pre_registration_fail(self):
        with self.assertRaises(ValidationError):
            RegularFlow().pre_registration({'artist_name': ''})

    def test_pre_registration_success(self):
        self.assertIsNone(RegularFlow().pre_registration({'artist_name': 'x'}))
