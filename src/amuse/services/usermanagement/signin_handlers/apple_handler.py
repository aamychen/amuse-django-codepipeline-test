from typing import Optional

from rest_framework.request import Request

from amuse.platform import PlatformHelper
from amuse.vendor.apple_signin import login as apple_authenticate
from users.models import User
from .base_handler import BaseSignInHandler


class AppleSignInHandler(BaseSignInHandler):
    def __init__(self, access_token: str, apple_signin_id: str):
        self.access_token = access_token
        self.apple_signin_id = apple_signin_id

    def authenticate(self, request: Request) -> Optional[User]:
        platform = PlatformHelper.from_request(request)

        authenticated = apple_authenticate(
            platform=platform,
            access_token=self.access_token,
            apple_signin_id=self.apple_signin_id,
        )

        if not authenticated:
            return None

        return User.objects.active.filter(apple_signin_id=self.apple_signin_id).first()
