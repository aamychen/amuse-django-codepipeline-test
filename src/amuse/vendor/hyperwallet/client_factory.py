from hyperwallet import Api
from django.conf import settings


class HyperWalletEmbeddedClientFactory(object):
    def __init__(self):
        self.user = settings.HW_EMBEDDED_USER
        self.password = settings.HW_EMBEDDED_PASSWORD
        self.program_token = settings.HW_EMBEDDED_PROGRAM_TOKEN_REST_OF_WORLD
        self.server = settings.HW_EMBEDDED_SERVER

    def create(self, country_code):
        if country_code == "SE":
            self.program_token = settings.HW_EMBEDDED_PROGRAM_TOKEN_SE
        if country_code in settings.EU_COUNTRIES_DIRECT:
            self.program_token = settings.HW_EMBEDDED_PROGRAM_TOKEN_EU

        return Api(
            username=self.user,
            password=self.password,
            programToken=self.program_token,
            server=self.server,
        )
