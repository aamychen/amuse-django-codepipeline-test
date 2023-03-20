import logging
from enum import Flag, auto, unique
from typing import Optional, List

from django.conf import settings
from django.db.models import Case, When, Value

from amuse.vendor.aws import sns
from amuse.vendor.segment.events import send_smart_link_delivered_email
from countries.country_codec import CountryCodec
from releases.models import Release

logger = logging.getLogger(__name__)


@unique
class SmartLinkStoreFlags(Flag):
    """Stores used by Amuse Smart Links service"""

    spotify = auto()
    apple = auto()
    deezer = auto()
    youtube_music = auto()
    tidal = auto()

    @classmethod
    def get_names(cls):
        return list(map(lambda s: s.name, SmartLinkStoreFlags))

    @classmethod
    def get_none(cls):
        return SmartLinkStoreFlags.spotify & SmartLinkStoreFlags.apple

    @classmethod
    def get_stores(self, release, smart_link_internal_names):
        stores = release.stores.filter(
            internal_name__in=smart_link_internal_names
        ).all()
        return stores

    @classmethod
    def get_release_flag(cls, release: Release) -> int:
        smart_link_internal_names = SmartLinkStoreFlags.get_names()
        stores = cls.get_stores(release, smart_link_internal_names)

        store_flag = SmartLinkStoreFlags.get_none()
        for store in stores:
            if store.internal_name in smart_link_internal_names:
                store_flag = store_flag | SmartLinkStoreFlags[store.internal_name]

        return int(store_flag.value)

    @classmethod
    def create_store_flags_dict(cls, release: Release) -> dict:
        smart_link_internal_names = SmartLinkStoreFlags.get_names()
        stores = cls.get_stores(release, smart_link_internal_names)

        store_flags_dict = dict.fromkeys(smart_link_internal_names, False)
        for store in stores:
            if store.internal_name in smart_link_internal_names:
                store_flags_dict[store.internal_name] = True

        return store_flags_dict


def send_smart_link_creation_data_to_link_service(message_batch: List[dict]) -> None:
    """
    Sends request for creating amuse smart links.
    Request is sent via AWS SNS service.

    :param message_batch: List of messages for smart link creation.
    """
    sns.sns_send_message(settings.AWS_SNS_SMART_LINK_TOPIC_ARN, message_batch)


def create_pre_release_smart_link_message_payload(release: Release) -> dict:
    """
    Creates message payload for release that haven't been released yet.

    This message payload is sent via AWS SNS to amuse-links backend
    that creates smart link out of this payload.
    :param release:
    :return:
    """
    item_type = translate_release_type_to_smart_link_service_type(release)
    artist = release.main_primary_artist

    song_id = None
    if item_type == 'track':
        song = release.songs.first()
        song_id = str(song.id)

    return dict(
        type=item_type,
        amuse_release_id=release.id,
        song_id=song_id,
        name=release.name,
        image=release.cover_art.thumbnail_url_400,
        artist_name=artist.name if artist else None,
        include_pre_save_link=release.include_pre_save_link,
        stores=SmartLinkStoreFlags.get_release_flag(release),
        status=release.status,
    )


def create_release_smart_link_message_payload(release: Release) -> dict:
    """
    Creates message payload for released Release.
    This message payload is sent via AWS SNS to amuse-links backend
    that creates smart link out of this payload.
    """
    item_type = translate_release_type_to_smart_link_service_type(release)
    artist = release.main_primary_artist

    isrc = None
    song_id = None
    if item_type == 'track':
        song = release.songs.first()
        isrc = str(song.isrc_code)
        song_id = str(song.id)

    countries_encoded = CountryCodec.encode(list(release.included_countries))

    return dict(
        type=item_type,
        amuse_release_id=release.id,
        song_id=song_id,
        name=release.name,
        image=release.cover_art.thumbnail_url_400,
        artist_name=artist.name if artist else None,
        isrc=isrc,
        upc=str(release.upc),
        countries_encoded=countries_encoded,
        stores=SmartLinkStoreFlags.get_release_flag(release),
        status=release.status,
    )


def translate_release_type_to_smart_link_service_type(
    release: Release,
) -> Optional[str]:
    item_type = release.get_type_display()
    return {'single': 'track', 'ep': 'album', 'album': 'album'}.get(item_type)


def amuse_smart_link_callback(message_batch: List[dict]) -> None:
    """
    This functions should be invoked upon receiving release data
    from smart link service.
    """
    cases = []
    release_ids = []

    for message in message_batch:
        amuse_release_id = int(message['amuse_release_id'])
        cases.append(When(id=amuse_release_id, then=Value(message['link'])))
        release_ids.append(amuse_release_id)

    Release.objects.filter(id__in=release_ids).update(link=Case(*cases))
    email_smart_link_delivered_releases(release_ids)


def email_smart_link_delivered_releases(release_ids):
    releases = Release.objects.filter(
        id__in=release_ids, status=Release.STATUS_DELIVERED, link__isnull=False
    )
    for release in releases:
        for user in set([release.user, release.created_by]):
            send_smart_link_delivered_email(
                user.id,
                release.link,
                release.include_pre_save_link,
                SmartLinkStoreFlags.create_store_flags_dict(release),
            )
