from rest_framework import serializers
from countries.models import Country


class CountrySerializer(serializers.ModelSerializer):
    vat_percentage = serializers.DecimalField(
        max_digits=4, decimal_places=2, source='vat_percentage_api'
    )

    class Meta:
        model = Country
        fields = ('code', 'name', 'region_code', 'vat_percentage')


class CountryV1Serializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = (
            'code',
            'name',
            'region_code',
            'is_hyperwallet_enabled',
            'dial_code',
            'is_yt_content_id_enabled',
            'is_signup_enabled',
        )
