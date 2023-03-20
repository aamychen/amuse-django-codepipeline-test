from rest_framework import serializers

from releases.models import StoreCategory


class StoreCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreCategory
        fields = ('name', 'order')
