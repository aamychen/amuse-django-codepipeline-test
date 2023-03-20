from django.db import transaction

from releases.models import AssetLabel, ReleaseAssetLabel, SongAssetLabel
from subscriptions.models import SubscriptionPlan
from users.models import User


class ReleaseAssetLabelBuilder(object):
    """
    Utility class for creating release and song default asset labels
    """

    LABEL_TYPE_USER = 1
    LABEL_TYPE_RELEASE = 2
    LABEL_TYPE_SONG = 3

    def __init__(self, release):
        self.release = release
        self.user = release.user
        self.songs = self.release.songs.all()

    def format_label(self, text):
        return text.translate(
            {ord(c): "_" for c in "!@#$%^&*()[]{};:,./<>?\|`~=+"}
        ).replace(" ", "_")

    def _get_user_tier_label(self):
        tier = self.user.tier
        if tier == User.TIER_FREE:
            return "free"
        if tier == SubscriptionPlan.TIER_PLUS:
            return "boost"
        return "pro"

    def collect_user_labels(self):
        user_labels = list()
        user_labels.append(self.user.country)
        user_labels.append(self._get_user_tier_label())

        return [user_label for user_label in user_labels if user_label]

    def collect_release_labels(self):
        release_labels = list()
        release_labels.append(self.release.get_type_display())
        user = self.release.user if self.release.user else self.release.created_by
        if user.category != User.CATEGORY_DEFAULT:
            release_labels.append(user.get_category_name() + '_user')
        return [release_label for release_label in release_labels if release_label]

    def collect_song_labels(self, song):
        song_labels = list()
        song_labels.append(self.format_label(song.genre.name))
        song_labels.append(song.get_origin_display())
        return [song_label for song_label in song_labels if song_label]

    def get_or_create_asset_labels(self, labels_type, song=None):
        labels_objs = list()
        if labels_type == self.LABEL_TYPE_USER:
            user_labels = self.collect_user_labels()
            for label in user_labels:
                obj, created = AssetLabel.objects.get_or_create(name=label.lower())
                labels_objs.append(obj)
            return labels_objs
        if labels_type == self.LABEL_TYPE_RELEASE:
            release_labels = self.collect_release_labels()
            for label in release_labels:
                obj, created = AssetLabel.objects.get_or_create(name=label.lower())
                labels_objs.append(obj)
            return labels_objs
        if labels_type == self.LABEL_TYPE_SONG:
            song_labels = self.collect_song_labels(song=song)
            for label in song_labels:
                obj, created = AssetLabel.objects.get_or_create(name=label.lower())
                labels_objs.append(obj)
            return labels_objs

    def create_release_asset_labels(self):
        asset_labels = self.get_or_create_asset_labels(self.LABEL_TYPE_RELEASE)
        release_asset_label_list = list()
        for asset_label in asset_labels:
            release_asset_label_list.append(
                ReleaseAssetLabel(release=self.release, asset_label=asset_label)
            )
        ReleaseAssetLabel.objects.bulk_create(release_asset_label_list)

    def create_song_asset_lables(self, song):
        song_asset_labels_obj = list()
        user_asset_labels = self.get_or_create_asset_labels(self.LABEL_TYPE_USER)
        song_asset_labels = self.get_or_create_asset_labels(self.LABEL_TYPE_SONG, song)
        all_labels = [*user_asset_labels, *song_asset_labels]
        for label in all_labels:
            song_asset_labels_obj.append(SongAssetLabel(song=song, asset_label=label))
        SongAssetLabel.objects.bulk_create(song_asset_labels_obj)

    @transaction.atomic
    def build_labels(self):
        self.create_release_asset_labels()
        for song in self.songs:
            self.create_song_asset_lables(song=song)
