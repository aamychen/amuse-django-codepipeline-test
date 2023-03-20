from unittest import mock

from django.test import TestCase

from amuse.api.v5.serializers.user import UserSerializer
from users.tests.factories import UserFactory, UserMetadataFactory
from payouts.tests.factories import PayeeFactory


class TestUserSerializer(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user")
    def setUp(self, mock_zendesk):
        self.user = UserFactory(is_frozen=True)
        self.serializer = UserSerializer()

    def test_is_fraud_attempted_is_true(self):
        UserMetadataFactory(user=self.user, is_fraud_attempted=True)
        serialized_user = self.serializer.to_representation(instance=self.user)
        assert serialized_user["is_fraud_attempted"] == True

    def test_is_fraud_attempted_is_false(self):
        serialized_user = self.serializer.to_representation(instance=self.user)
        assert serialized_user["is_fraud_attempted"] == False

    def test_has_hyperwallet_token_is_true(self):
        UserMetadataFactory(user=self.user, hyperwallet_user_token="xxxx")
        serialized_user = self.serializer.to_representation(instance=self.user)
        assert serialized_user["has_hyperwallet_token"] is True

    def test_has_hyperwallet_token_is_false(self):
        UserMetadataFactory(user=self.user, hyperwallet_user_token=None)
        serialized_user = self.serializer.to_representation(instance=self.user)
        assert serialized_user["has_hyperwallet_token"] is False

    def test_has_tier_property(self):
        serialized_user = self.serializer.to_representation(self.user)
        assert serialized_user['tier'] == 0

    def test_has_is_frozen_property(self):
        serialized_user = self.serializer.to_representation(self.user)
        assert serialized_user['is_frozen'] == True

    def test_hyperwaallet_integration_direct(self):
        self.user.country = 'TR'
        self.user.save()
        serialized_user = self.serializer.to_representation(self.user)
        assert serialized_user['hyperwallet_integration'] == 'direct'

    def test_payee_profile_exist(self):
        serialized_user = self.serializer.to_representation(self.user)
        assert serialized_user['payee_profile_exist'] == False
        # Create Payee and repeat test
        PayeeFactory(user=self.user)
        serialized_user = self.serializer.to_representation(self.user)
        assert serialized_user['payee_profile_exist'] == True
