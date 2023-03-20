from django.apps import AppConfig
from django.conf import settings
from slayer.clientwrapper import slayer


class SlayerConfig(AppConfig):
    name = 'slayer'

    def ready(self):
        slayer.channel_configure(
            host=settings.SLAYER_GRPC_HOST,
            port=settings.SLAYER_GRPC_PORT,
            ssl_mode=settings.SLAYER_GRPC_SSL,
        )
        slayer.sync_init()
