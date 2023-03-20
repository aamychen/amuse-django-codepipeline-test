import responses
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase, override_settings
from releases.tests.factories import ReleaseFactory, AssetLabelFactory, SongFactory
from releases.models import ReleaseAssetLabel, AssetLabel, Song
from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class ReleaseAssetLabelTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.release = ReleaseFactory()
        self.song = SongFactory()
        self.asset_labels = ["pro", "jazz", "signedartist", 'ca', "usa", "de"]
        for label in self.asset_labels:
            AssetLabelFactory(name=label)

    def test_validation(self):
        label = AssetLabelFactory()
        label.name = "No space allowed"
        self.assertRaises(ValidationError, label.full_clean)
        label.name = "No$pecialCharacters"
        self.assertRaises(ValidationError, label.full_clean)
        label.name = "a"
        self.assertRaises(ValidationError, label.full_clean)

        # Assert positive case
        label.name = "ThisISValid"
        label.save()
        label.refresh_from_db()
        self.assertEqual(label.name, "ThisISValid".lower())

        # Assert delimters are allowed
        label.name = "This_is_nice_label"
        label.save()
        label.refresh_from_db()
        self.assertEqual(label.name, "This_is_nice_label".lower())

        # Assert delimters are allowed
        label.name = "This-is-nice-label"
        label.save()
        label.refresh_from_db()
        self.assertEqual(label.name, "This-is-nice-label".lower())

    def test_get_or_create(self):
        existing_label, created = AssetLabel.objects.get_or_create(name='jazz')
        all_labels = AssetLabel.objects.all()
        assert all_labels.count() == 6
        assert existing_label.name == "jazz"
        assert created == False

        # Assert uniq constraint
        with self.assertRaises(Exception) as raised:
            AssetLabel.objects.create(name="jazz")
        self.assertEqual(IntegrityError, type(raised.exception))

    def test_create_release_lables(self):
        labels = AssetLabel.objects.all()
        for asset_label in labels:
            self.release.asset_labels.create(asset_label=asset_label)

        release_asset_lables = self.release.asset_labels.all()
        (release_asset_lables.count(), 6)

    def test_uniq_together_constrain(self):
        release_label = AssetLabel.objects.all().first()
        self.release.asset_labels.create(asset_label=release_label)
        with self.assertRaises(Exception) as raised:
            self.release.asset_labels.create(asset_label=release_label)
        self.assertEqual(IntegrityError, type(raised.exception))

    def test_song_asset_lables(self):
        labels = AssetLabel.objects.all()
        for asset_label in labels:
            self.song.asset_labels.create(asset_label=asset_label)

        song_asset_lables = self.song.asset_labels.all()
        (song_asset_lables.count(), 6)

    def test_uniq_together_constrain_song(self):
        song_label = AssetLabel.objects.all().first()
        self.song.asset_labels.create(asset_label=song_label)
        with self.assertRaises(Exception) as raised:
            self.song.asset_labels.create(asset_label=song_label)
        self.assertEqual(IntegrityError, type(raised.exception))
