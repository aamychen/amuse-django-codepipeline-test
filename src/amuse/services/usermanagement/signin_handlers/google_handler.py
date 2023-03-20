from typing import Optional

import requests
from rest_framework.request import Request

from users.models import User
from .base_handler import BaseSignInHandler


class GoogleSignInHandler(BaseSignInHandler):
    def __init__(self, google_id: str, google_id_token: str):
        self.google_id = google_id
        self.google_id_token = google_id_token
        self.url = 'https://www.googleapis.com/oauth2/v3/tokeninfo'

    def authenticate(self, request: Request) -> Optional[User]:
        r = requests.get(self.url, params={'id_token': self.google_id_token})

        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            return None

        u = r.json()
        if not u or u.get('sub') != self.google_id:
            return None

        user = User.objects.active.filter(google_id=self.google_id).first()
        if not user:
            return None

        if not user.first_name or not user.last_name:
            user.first_name = u.get('given_name')
            user.last_name = u.get('family_name')
            user.save()

        return user
