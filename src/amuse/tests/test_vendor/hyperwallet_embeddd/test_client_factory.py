from django.test import TestCase
from django.conf import settings
from hyperwallet import Api
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory


class ClientFactoryTestCase(TestCase):
    def test_create(self):
        se_program_client = HyperWalletEmbeddedClientFactory().create("SE")
        eu_program_client = HyperWalletEmbeddedClientFactory().create("FR")
        world_program_client = HyperWalletEmbeddedClientFactory().create("TR")
        gb_program_client = HyperWalletEmbeddedClientFactory().create("GB")

        self.assertIsInstance(se_program_client, Api)
        self.assertIsInstance(eu_program_client, Api)
        self.assertIsInstance(world_program_client, Api)
        self.assertIsInstance(gb_program_client, Api)

        self.assertEqual(
            eu_program_client.programToken, settings.HW_EMBEDDED_PROGRAM_TOKEN_EU
        )
        self.assertEqual(
            se_program_client.programToken, settings.HW_EMBEDDED_PROGRAM_TOKEN_SE
        )
        self.assertEqual(
            world_program_client.programToken,
            settings.HW_EMBEDDED_PROGRAM_TOKEN_REST_OF_WORLD,
        )
        self.assertEqual(
            gb_program_client.programToken,
            settings.HW_EMBEDDED_PROGRAM_TOKEN_REST_OF_WORLD,
        )
