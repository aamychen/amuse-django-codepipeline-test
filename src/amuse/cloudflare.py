import json
import jwt
from django.conf import settings
from logging import getLogger
from users.models import User

logger = getLogger(__name__)


class CloudflareAccessAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        headers = request.META

        if (token := self.extract_jwt(headers)) == None:
            return self.get_response(request)

        if (username := self.extract_username(headers)) == None:
            return self.get_response(request)

        if (email := self.verify_jwt_token(token)) is None:
            logger.error("Invalid token for username %s", username)
            return self.get_response(request)

        if username != email:
            logger.error("Mistmatching username and email %s / %s", username, email)
            return self.get_response(request)

        if (user := User.objects.filter(email=email).first()) is None:
            logger.error("Found no local user with email %s", email)
            return self.get_response(request)

        request.user = user

        return self.get_response(request)

    def extract_jwt(self, headers):
        return headers.get("HTTP_CF_ACCESS_JWT_ASSERTION", None)

    def extract_username(self, headers):
        return headers.get("HTTP_CF_ACCESS_AUTHENTICATED_USER_EMAIL", None)

    def read_public_keys(self):
        public_keys = []
        with open(settings.CLOUDFLARE_CERTS, "rb") as file:
            contents = file.read().decode("utf-8")
            contents_dict = json.loads(contents)
            for key in contents_dict["keys"]:
                key_str = json.dumps(key)
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_str)
                public_keys.append(public_key)
        return public_keys

    def verify_jwt_token(self, token):
        public_keys = self.read_public_keys()
        for public_key in public_keys:
            try:
                decoded_key = jwt.decode(
                    token,
                    key=public_key,
                    audience=settings.CLOUDFLARE_AUD,
                    algorithms=["RS256"],
                )
                return decoded_key["email"]
            except Exception as e:
                logger.exception(e)
        return None
