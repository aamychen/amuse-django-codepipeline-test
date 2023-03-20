import responses
from django.test import TestCase, override_settings

from amuse.tests.helpers import (
    ZENDESK_MOCK_API_URL_TOKEN,
    add_zendesk_mock_post_response,
)
from releases.asset_labels.builder import ReleaseAssetLabelBuilder
from releases.models import AssetLabel
from releases.tests.factories import ReleaseFactory, SongFactory
from users.models import User, UserMetadata
from users.tests.factories import UserFactory, UserMetadataFactory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class AssetLabelBuilderTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        self.user = UserFactory(country='BA')
        self.release = ReleaseFactory(user=self.user)
        self.song = SongFactory(release=self.release)
        self.builder = ReleaseAssetLabelBuilder(release=self.release)

    def test_label_formatter(self):
        test_a = "Hip Hop/Rap"
        formatted_a = self.builder.format_label(test_a).lower()
        assert formatted_a == "hip_hop_rap"

    def test_data_collectors(self):
        sl = self.builder.collect_song_labels(song=self.song)
        ul = self.builder.collect_user_labels()
        rl = self.builder.collect_release_labels()
        self.assertIsNotNone(sl)
        self.assertIsNotNone(ul)
        self.assertIsNotNone(rl)

    def test_asset_label_get_or_create(self):
        user_asset_labels = self.builder.get_or_create_asset_labels(
            ReleaseAssetLabelBuilder.LABEL_TYPE_USER
        )
        for al in user_asset_labels:
            assert isinstance(al, AssetLabel)

        release_asset_labels = self.builder.get_or_create_asset_labels(
            ReleaseAssetLabelBuilder.LABEL_TYPE_RELEASE
        )
        for rl in release_asset_labels:
            assert isinstance(rl, AssetLabel)

        song_asset_labels = self.builder.get_or_create_asset_labels(
            ReleaseAssetLabelBuilder.LABEL_TYPE_SONG, song=self.song
        )
        for sl in song_asset_labels:
            assert isinstance(sl, AssetLabel)

    def test_build_labels(self):
        self.builder.build_labels()
        release_labels_db = self.release.asset_labels.all()
        song_labels_db = self.song.asset_labels.all()
        assert release_labels_db.count() > 0
        assert song_labels_db.count() > 0

    def test_non_default_category_user_release_label_added(self):
        for category in [
            User.CATEGORY_PRIORITY,
            User.CATEGORY_QUALIFIED,
            User.CATEGORY_FLAGGED,
        ]:
            self.user.category = category
            self.user.save()
            release = ReleaseFactory(user=self.user, created_by=self.user)
            builder = ReleaseAssetLabelBuilder(release=release)

            label_name = self.user.get_category_name() + '_user'

            builder.build_labels()
            release_labels = [
                label.asset_label.name for label in release.asset_labels.all()
            ]

            self.assertTrue(AssetLabel.objects.filter(name=label_name).exists())
            self.assertIn(label_name, release_labels)

    def test_flagged_user_label_added(self):
        self.user.category = User.CATEGORY_FLAGGED
        self.user.save()

        self.builder.build_labels()
        release_labels = [
            label.asset_label.name for label in self.release.asset_labels.all()
        ]

        self.assertTrue(AssetLabel.objects.filter(name='flagged_user').exists())
        self.assertIn('flagged_user', release_labels)
