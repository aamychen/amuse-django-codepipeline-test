from django.http import JsonResponse
from django.utils import timezone
from rest_framework import serializers, status

from amuse.utils import CLIENT_ANDROID, CLIENT_IOS, parse_client_version
from users.models import AppsflyerDevice


class AppsflyerDeviceSerializer(serializers.Serializer):
    appsflyer_id = serializers.CharField(max_length=64, allow_null=False, required=True)
    idfa = serializers.CharField(max_length=36, allow_null=True, required=False)
    idfv = serializers.CharField(max_length=36, allow_null=True, required=False)
    aaid = serializers.CharField(max_length=36, allow_null=True, required=False)
    oaid = serializers.CharField(max_length=36, allow_null=True, required=False)
    imei = serializers.CharField(max_length=20, allow_null=True, required=False)

    def validate(self, attrs):
        platform = parse_client_version(
            self.context['request'].META.get('HTTP_USER_AGENT') or ''
        )[0]
        if platform == CLIENT_IOS:
            return self._validate_one_of(attrs, ['idfv', 'idfa'])

        if platform == CLIENT_ANDROID:
            return self._validate_one_of(attrs, ['aaid', 'oaid', 'imei'])

        return attrs

    def _validate_one_of(self, attrs, fields):
        for field in fields:
            if attrs.get(field) is not None:
                return attrs

        raise serializers.ValidationError(
            f'At least one of the following fields is required: {fields}'
        )

    def create(self, **kwargs):
        user = self.context['request'].user

        body = self.validated_data

        AppsflyerDevice.objects.create(
            user=user,
            appsflyer_id=body.get('appsflyer_id'),
            idfa=body.get('idfa'),
            idfv=body.get('idfv'),
            aaid=body.get('aaid'),
            oaid=body.get('oaid'),
            imei=body.get('imei'),
            updated=timezone.now(),
        )
        return JsonResponse({}, status=status.HTTP_201_CREATED)

    def update(self, instance, **kwargs):
        body = self.validated_data

        if body.get('idfa'):
            instance.idfa = body.get('idfa')

        if body.get('idfv'):
            instance.idfv = body.get('idfv')

        if body.get('aaid'):
            instance.aaid = body.get('aaid')

        if body.get('oaid'):
            instance.oaid = body.get('oaid')

        if body.get('imei'):
            instance.imei = body.get('imei')

        instance.updated = timezone.now()

        instance.save()
        return JsonResponse({}, status=status.HTTP_200_OK)
