from typing import Optional

from django.contrib.auth import authenticate
from rest_framework.request import Request

from users.models import User
from .base_handler import BaseSignInHandler


class EmailSignInHandler(BaseSignInHandler):
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def authenticate(self, request: Request) -> Optional[User]:
        return authenticate(username=self.username, password=self.password)
