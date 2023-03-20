from typing import Optional

import requests
from rest_framework.request import Request

from users.models import User
from .base_handler import BaseSignInHandler


class FacebookSignInHandler(BaseSignInHandler):
    def __init__(self, facebook_id: str, facebook_access_token: str):
        self.facebook_id = facebook_id
        self.facebook_access_token = facebook_access_token

    def authenticate(self, request: Request) -> Optional[User]:
        r = requests.get(
            'https://graph.facebook.com/v8.0/me',
            params={
                'access_token': self.facebook_access_token,
                'fields': 'first_name,last_name',
            },
        )

        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            return None

        u = r.json()
        if not u or u.get('id') != self.facebook_id:
            return None

        user = User.objects.active.filter(facebook_id=self.facebook_id).first()
        if not user:
            return None

        if not user.first_name or not user.last_name:
            user.first_name = u.get('first_name')
            user.last_name = u.get('last_name')
            user.save()

        return user
