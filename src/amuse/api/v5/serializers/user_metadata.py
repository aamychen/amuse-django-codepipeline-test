from rest_framework import serializers


class UserMetadataSerializer(serializers.Serializer):
    impact_click_id = serializers.CharField(
        max_length=128, allow_null=True, allow_blank=True, required=False
    )
