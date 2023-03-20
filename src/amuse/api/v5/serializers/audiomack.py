import logging

from rest_framework import serializers

logger = logging.getLogger(__name__)


class AudiomackOauthSerializer(serializers.Serializer):
    artist_id = serializers.IntegerField(required=True)


class AudiomackCallbackSerializer(serializers.Serializer):
    oauth_token = serializers.CharField(required=True)
    oauth_verifier = serializers.CharField(required=True)
    platform = serializers.IntegerField()
