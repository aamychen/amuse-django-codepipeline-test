from rest_framework import permissions
from rest_framework.views import APIView

from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.api.v6.serializers import LoginSerializer
from amuse.permissions import ReCaptchaPermission
from amuse.services.usermanagement import UserLoginService
from amuse.throttling import LoginEndpointThrottle


class LoginView(APIView):
    permission_classes = [permissions.AllowAny, ReCaptchaPermission]
    throttle_classes = [LoginEndpointThrottle]

    def post(self, request):
        if request.version != '6':
            raise WrongAPIversionError

        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return UserLoginService().email(
            request,
            serializer.validated_data['email'],
            serializer.validated_data['password'],
        )
