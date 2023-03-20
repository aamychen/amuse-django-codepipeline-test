from amuse.deliveries import *
from .audiomack_check import AudiomackCheck
from .ffwd_release_check import FFWDReleaseCheck
from .ffwd_user_check import FFWDUserCheck
from .fuga_check import FugaCheck
from .is_live_on_store_check import IsLiveOnStoreCheck
from .licensed_check import LicensedCheck
from .pro_store_check import ProStoreCheck
from .explicit_delivery_check import ExplicitReleaseCheck
from .youtube_cid_flagged_user_check import YoutubeCIDFlaggedUserCheck
from .youtube_cid_live_on_youtube_check import YoutubeCIDLiveOnYouTubeCheck
from .youtube_cid_monetization_check import YoutubeCIDMonetizationCheck
from .frozen_user_check import FrozenUserCheck

ALL_STORE_CHECKS = [
    FrozenUserCheck,
    ProStoreCheck,
    IsLiveOnStoreCheck,
    FugaCheck,
    FFWDReleaseCheck,
    FFWDUserCheck,
    LicensedCheck,
]

SPECIFIC_STORE_CHECKS = {
    CHANNELS[FUGA]: [],
    CHANNELS[APPLE]: [],
    CHANNELS[SPOTIFY]: [],
    CHANNELS[TIKTOK]: [],
    CHANNELS[SOUNDCLOUD]: [],
    CHANNELS[SEVENDIGITAL]: [],
    CHANNELS[AMAZON]: [],
    CHANNELS[ANGHAMI]: [],
    CHANNELS[CLARO_MUSICA]: [],
    CHANNELS[DEEZER]: [],
    CHANNELS[NUUDAY]: [],
    CHANNELS[TIDAL]: [],
    CHANNELS[YOUTUBE_CONTENT_ID]: [
        YoutubeCIDMonetizationCheck,
        YoutubeCIDFlaggedUserCheck,
        YoutubeCIDLiveOnYouTubeCheck,
    ],
    CHANNELS[YOUTUBE_MUSIC]: [],
    CHANNELS[FACEBOOK]: [],
    CHANNELS[TWITCH]: [],
    CHANNELS[SHAZAM]: [],
    CHANNELS[AUDIOMACK]: [AudiomackCheck],
    CHANNELS[BOOMPLAY]: [],
    CHANNELS[PANDORA]: [],
    CHANNELS[KKBOX]: [],
    CHANNELS[TENCENT]: [ExplicitReleaseCheck],
    CHANNELS[IHEART]: [],
    CHANNELS[NETEASE]: [ExplicitReleaseCheck],
}

_LIST_OF_LISTS = [SPECIFIC_STORE_CHECKS[store] for store in SPECIFIC_STORE_CHECKS]
SPECIFIC_STORE_CHECKS_LIST = [check for checks in _LIST_OF_LISTS for check in checks]
ALL_DELIVERY_CHECKS = ALL_STORE_CHECKS + SPECIFIC_STORE_CHECKS_LIST


def get_store_delivery_checks(store):
    return ALL_STORE_CHECKS + SPECIFIC_STORE_CHECKS.get(store, [])
