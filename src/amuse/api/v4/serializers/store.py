from rest_framework import serializers

from releases.models import Store
from amuse.api.v4.serializers.store_category import StoreCategorySerializer


class StoreSerializer(serializers.ModelSerializer):
    category = StoreCategorySerializer()
    hex_color = serializers.RegexField(
        regex=r'^#?([a-fA-F\d]{3,4}|[a-fA-F\d]{6}|[a-fA-F\d]{8})$',
        error_messages={
            'invalid': 'Must be hexadecimal RGB string: (#RGB, #RRGGBB or #RRGGBBAA)'
        },
        required=False,
    )
    slug = serializers.SlugField(required=False)

    class Meta:
        model = Store
        fields = '__all__'
