import json
import pathlib

from django.test import TestCase

from releases.tests.factories import FugaArtistFactory

absolute_src_path = pathlib.Path(__file__).parent.parent.parent.resolve()


def load_fixture(filename):
    return open(f"{absolute_src_path}/amuse/tests/test_vendor/fixtures/{filename}")


class FugaArtistTestCase(TestCase):
    def setUp(self):
        self.fuga_artist = FugaArtistFactory()
        self.organizations_for_artist = json.load(
            load_fixture("FugaArtistIdentifier.json")
        )

    def test_parse_organizations(self):
        self.assertIsNone(self.fuga_artist.parsed_at)
        self.assertIsNone(self.fuga_artist.apple_id)
        self.assertIsNone(self.fuga_artist.spotify_id)

        self.fuga_artist.parse_organizations(self.organizations_for_artist)
        self.fuga_artist.refresh_from_db()

        self.assertTrue(self.fuga_artist.parsed_at)
        self.assertEqual("1122334455", self.fuga_artist.apple_id)
        self.assertEqual("spotify:artist:identifier", self.fuga_artist.spotify_id)
