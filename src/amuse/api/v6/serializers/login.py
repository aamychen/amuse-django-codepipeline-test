import logging

from rest_framework import serializers

logger = logging.getLogger(__name__)


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(required=True, write_only=True)
    password = serializers.CharField(required=True, write_only=True)


class GoogleLoginSerializer(serializers.Serializer):
    google_id = serializers.CharField(required=True, write_only=True)
    google_id_token = serializers.CharField(required=True, write_only=True)


class AppleLoginSerializer(serializers.Serializer):
    access_token = serializers.CharField(required=True, write_only=True)
    apple_signin_id = serializers.CharField(required=True, write_only=True)


class FacebookLoginSerializer(serializers.Serializer):
    facebook_id = serializers.CharField(required=True, write_only=True)
    facebook_access_token = serializers.CharField(required=True, write_only=True)
