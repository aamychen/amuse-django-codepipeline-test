from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated

from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v5.serializers.appsflyer_device import AppsflyerDeviceSerializer
from users.models import AppsflyerDevice


class AppsflyerDeviceView(CreateAPIView):
    serializer_class = AppsflyerDeviceSerializer
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.request.version == '5':
            raise WrongAPIversionError()

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device = AppsflyerDevice.objects.filter(
            appsflyer_id=serializer.validated_data['appsflyer_id']
        ).first()
        if device is None:
            return serializer.create()

        return serializer.update(device)
