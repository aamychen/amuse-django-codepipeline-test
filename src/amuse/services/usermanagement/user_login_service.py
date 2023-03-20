import abc
from typing import Literal

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from amuse.api.base.cookies import set_otp_cookie, set_access_cookie, set_refresh_cookie
from amuse.api.helpers import send_login_succeeded, is_2fa_enabled
from amuse.tasks import refresh_spotify_artist_images
from .signin_handlers import (
    AppleSignInHandler,
    BaseSignInHandler,
    EmailSignInHandler,
    FacebookSignInHandler,
    GoogleSignInHandler,
)


class UserLoginService(abc.ABC):
    def social_login(
        self,
        request: Request,
        kind: Literal['google', 'facebook', 'apple'],
        validated_data: dict,
    ):
        if kind == 'google':
            return self.google(
                request, validated_data['google_id'], validated_data['google_id_token']
            )

        if kind == 'facebook':
            return self.facebook(
                request,
                validated_data['facebook_id'],
                validated_data['facebook_access_token'],
            )

        if kind == 'apple':
            return self.apple(
                request,
                validated_data['access_token'],
                validated_data['apple_signin_id'],
            )

        raise ValueError(f"invalid 'kind' value. kind={kind}")

    def facebook(
        self, request: Request, facebook_id: str, facebook_access_token: str
    ) -> Response:
        handler = FacebookSignInHandler(facebook_id, facebook_access_token)
        return self._common(request, handler)

    def google(
        self, request: Request, google_id: str, google_id_token: str
    ) -> Response:
        handler = GoogleSignInHandler(google_id, google_id_token)
        return self._common(request, handler)

    def apple(
        self, request: Request, access_token: str, apple_signin_id: str
    ) -> Response:
        handler = AppleSignInHandler(access_token, apple_signin_id)
        return self._common(request, handler)

    def email(self, request: Request, username: str, password: str) -> Response:
        handler = EmailSignInHandler(username, password)
        return self._common(request, handler)

    def _common(self, request: Request, signin_handler: BaseSignInHandler) -> Response:
        user = signin_handler.authenticate(request)

        if not user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        if user.is_delete_requested:
            return Response(
                {'email': 'User is deleted'}, status=status.HTTP_400_BAD_REQUEST
            )

        response = Response(data={}, status=status.HTTP_200_OK)
        if is_2fa_enabled(request, user):
            set_otp_cookie(response, user.id)
        else:
            set_access_cookie(response, user.id)
            set_refresh_cookie(response, user.id)

        if user.has_artist_with_spotify_id():
            refresh_spotify_artist_images.delay(user.id)

        send_login_succeeded(request, user)

        return response
