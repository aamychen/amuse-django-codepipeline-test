from django.core.management.base import BaseCommand
from django.conf import settings
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory


class Command(BaseCommand):
    def handle(self, *args, **options):
        """
        Smoke test for Hyperwallet Direct integration including:
        Test client factory
        Test all settings are in place
        Test access to HW api per program (EU, SE, REST_OF_WORLD)
        """
        client_world = HyperWalletEmbeddedClientFactory().create("US")
        client_eu = HyperWalletEmbeddedClientFactory().create("FR")
        client_se = HyperWalletEmbeddedClientFactory().create("SE")

        print("Testing Direct Programs")
        name_world = client_world.getProgram(
            programToken=settings.HW_EMBEDDED_PROGRAM_TOKEN_REST_OF_WORLD
        ).name
        name_eu = client_eu.getProgram(
            programToken=settings.HW_EMBEDDED_PROGRAM_TOKEN_EU
        ).name
        name_se = client_se.getProgram(
            programToken=settings.HW_EMBEDDED_PROGRAM_TOKEN_SE
        ).name

        print(f'EU: {name_eu}')
        print(f'SE: {name_se}')
        print(f'WORLD: {name_world}')
