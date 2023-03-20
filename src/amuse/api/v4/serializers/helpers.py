import logging
import re
from decimal import Decimal

from django.utils import timezone
from django.db import IntegrityError
from releases.models.song import SongArtistRole
from releases.models.royalty_split import RoyaltySplit
from users.models.artist_v2 import ArtistV2
from users.models.royalty_invitation import RoyaltyInvitation
from users.models import User, UserArtistRole
from users.models.song_artist_invitation import SongArtistInvitation
from amuse.tokens import user_invitation_token_generator
from amuse import tasks
from amuse.vendor.spotify import SpotifyAPI
from users.helpers import send_royalty_invite
from django.db import transaction


spotifyAPI = SpotifyAPI()
logger = logging.getLogger(__name__)


def create_song_artists_roles(song, artists_roles_list, main_primary_artist_id):
    """
    Note that this creates arbitrary ordering within the same roles by design.

    Outcome 1:
        artist_1, featured_artist, artist_sequence=3
        artist_2, featured_artist, artist_sequence=4

    Outcome 2:
        artist_1, featured_artist, artist_sequence=4
        artist_2, featured_artist, artist_sequence=3
    """
    get_role_for_keyword = SongArtistRole.get_role_for_keyword

    sars = set()
    for artist_role in artists_roles_list:
        artist_id = artist_role['artist_id']

        # unique role values
        roles = set([get_role_for_keyword(name) for name in artist_role['roles']])

        for role in roles:
            # unique song-artist-role values
            sars.add((song.id, artist_id, role))

    song_artist_roles = []
    main_primary_artist_role = None

    for sar in list(sars):
        if (
            sar[1] == main_primary_artist_id
            and sar[2] == SongArtistRole.ROLE_PRIMARY_ARTIST
        ):
            main_primary_artist_role = SongArtistRole(
                song_id=sar[0], artist_id=sar[1], role=sar[2], artist_sequence=1
            )
        else:
            song_artist_roles.append(
                SongArtistRole(song_id=sar[0], artist_id=sar[1], role=sar[2])
            )

    # enforce artist_sequence
    song_artist_roles.sort(key=lambda item: item.role)
    for index, item in enumerate(song_artist_roles, 1):
        item.artist_sequence = index + 1

    song_artist_roles.insert(0, main_primary_artist_role)

    SongArtistRole.objects.bulk_create(song_artist_roles)


def notify_release_owner_if_required(inviter, song, royalty_splits, artist):
    is_owner = UserArtistRole.objects.filter(
        user=inviter, artist=artist, type=UserArtistRole.OWNER
    ).exists()

    if is_owner:
        return

    owner_role = UserArtistRole.objects.filter(
        artist=artist, type=UserArtistRole.OWNER
    ).first()

    if not owner_role:
        # if (for ANY reason) there is no owner role, do nothing
        return

    for royalty_split in royalty_splits:
        rate = royalty_split['rate']
        if rate != Decimal(1.0):
            tasks.send_royalty_owner_notification_email.delay(
                owner_role.user.id,
                owner_role.user.get_full_name(),
                song.name,
                inviter.first_name,
                inviter.last_name,
                rate,
            )
            return


def update_splits_state(song, latest_revision):
    today = timezone.now().today()

    all_splits = RoyaltySplit.objects.filter(song=song).order_by("-revision")
    existing_splits = all_splits.exclude(revision=latest_revision)
    new_splits = all_splits.filter(revision=latest_revision)

    if new_splits.revision_is_confirmed():
        new_splits.activate()

        currently_active_splits = existing_splits.filter(
            status=RoyaltySplit.STATUS_ACTIVE
        ).exclude(start_date=today)

        if currently_active_splits.exists():
            currently_active_splits.archive()

        same_day_active_splits = existing_splits.filter(
            status=RoyaltySplit.STATUS_ACTIVE, start_date=today
        )

        if same_day_active_splits.exists():
            logger.info("Deleted same day splits %s" % same_day_active_splits.values())
            same_day_active_splits.delete()

    inactive_splits = existing_splits.filter(
        status__in=[RoyaltySplit.STATUS_PENDING, RoyaltySplit.STATUS_CONFIRMED]
    )

    if inactive_splits.exists():
        logger.info("Deleted inactive splits %s" % inactive_splits.values())
        inactive_splits.delete()

    updated_existing_splits = (
        RoyaltySplit.objects.filter(song=song)
        .exclude(revision=latest_revision)
        .order_by("-revision")
    )

    if updated_existing_splits.exists():
        updated_revision = updated_existing_splits[0].revision + 1
    else:
        updated_revision = 1

    logger.info(
        "Updated revision to %s for splits for song_id %s" % (updated_revision, song.id)
    )
    new_splits.update(revision=updated_revision)


def update_royalty_splits(inviter, song, royalty_splits):
    revision = song.get_next_royalty_split_revision()
    start_date = timezone.now().today()

    args = {
        'inviter': inviter,
        'song': song,
        'royalty_splits': royalty_splits,
        'start_date': start_date,
        'revision': revision,
    }

    create_revision_of_royalty_splits(args, send_invite=True)

    new_splits = RoyaltySplit.objects.filter(song=song, revision=revision)
    update_splits_state(song, revision)


def create_royalty_splits(inviter, song, royalty_splits):
    """
    Creates RoyaltySplits instance.

    Args:
    ----
        inviter (User): User instance will be used when invite should be
            created.
        song (Song): Song insatnce will be used to create a RoyaltSplit.
        royalty_splits (list): List of dictionaries with the following keys,
            rate and user_id or rata and invite dictionary if user_id was not
            provided.
    """
    splits_exists = RoyaltySplit.objects.filter(song=song)

    if splits_exists:
        raise RoyaltySplitFirstRevisionExistsError(
            "Splits already exists. Use update_royalty_splits instead"
        )

    revision = 1
    start_date = None

    args = {
        'inviter': inviter,
        'song': song,
        'royalty_splits': royalty_splits,
        'start_date': start_date,
        'revision': revision,
    }

    create_revision_of_royalty_splits(args)

    new_splits = RoyaltySplit.objects.filter(song=song, revision=revision)

    if new_splits.revision_is_confirmed():
        new_splits.activate()


def create_revision_of_royalty_splits(args, send_invite=False):
    royalty_splits = args['royalty_splits']
    inviter = args['inviter']
    song = args['song']
    start_date = args['start_date']
    revision = args['revision']

    owner = song.release.main_primary_artist.owner

    for royalty_split in royalty_splits:
        rate = royalty_split['rate']
        user_id = royalty_split.get('user_id')
        invitee = None if user_id is None else User.objects.get(id=user_id)
        invite_dict = royalty_split.get('invite', None)

        is_same_user = invitee and inviter == invitee
        is_owner = owner == invitee if invitee else False

        status = (
            RoyaltySplit.STATUS_CONFIRMED
            if is_same_user or is_owner
            else RoyaltySplit.STATUS_PENDING
        )

        royalty_split = RoyaltySplit.objects.create(
            user=invitee,
            song=song,
            rate=rate,
            start_date=start_date,
            revision=revision,
            status=status,
            is_owner=is_owner,
        )

        should_not_create_invite = is_same_user or is_owner
        if should_not_create_invite:
            continue

        # create invite for everyone, except for owner and yourself
        create_invite(song, inviter, invitee, royalty_split, invite_dict, send_invite)


def create_invite(song, inviter, invitee, split, invite_dict, send_invite=False):
    token = None

    if send_invite:
        payload = {'inviter_id': song.release.user.id, 'split_id': split.id}
        token = user_invitation_token_generator.make_token(payload)

    email = invite_dict.get("email") if invitee is None else invitee.email
    phone = invite_dict.get("phone_number") if invitee is None else invitee.phone
    name = invite_dict.get("name") if invitee is None else invitee.name

    invite = RoyaltyInvitation.objects.create(
        inviter=inviter,
        invitee=invitee,
        royalty_split=split,
        email=email,
        phone_number=phone,
        name=name,
        token=token,
    )

    if send_invite:
        send_royalty_invite(invite, split, token)


def create_song_artist_invites(user, song, artists_invites_list):
    for invite in artists_invites_list:
        invitee_artist = ArtistV2.objects.get(id=invite.get('artist_id'))
        payload = {
            'user_id': user.id,
            'song_id': song.id,
            'artist_id': invitee_artist.id,
            'artist_name': invitee_artist.name,
        }
        token = user_invitation_token_generator.make_token(payload)

        SongArtistInvitation.objects.create(
            inviter=user,
            artist=ArtistV2.objects.get(id=invite.get('artist_id')),
            song=song,
            email=invite.get('email'),
            phone_number=invite.get('phone_number'),
            token=token,
            status=SongArtistInvitation.STATUS_CREATED,
        )


def fetch_spotify_image(spotify_id, default_image_url):
    """
    Based on spotify_id, the function will fetch largest spotify artist image url OR
    it will fallback to the default image url.
    Spotify provides several sizes of the same artist image.
    Default_spotify image is url pointing to the smallest spotify artist image.
    Default image is fetched by slayer
    (for some reason slayer selects the smallest image)
    """
    if not spotify_id:
        return default_image_url

    spotify_image = spotifyAPI.fetch_spotify_artist_image_url(spotify_id)

    if not spotify_image:
        return default_image_url

    return spotify_image


def is_valid_split_for_free_user(splits, owner_id):
    if len(splits) == 1:
        split = splits[0]
        return split['user_id'] == owner_id and split['rate'] == Decimal('1.0000')
    return False


def get_serialized_royalty_splits(song):
    return [
        {
            'name': royalty_split.get_user_name(),
            'photo': royalty_split.get_user_profile_photo_url(),
            'rate': float(royalty_split.rate),
        }
        for royalty_split in song.royalty_splits.exclude(
            status=RoyaltySplit.STATUS_CANCELED
        )
    ]


def get_serialized_active_royalty_splits(song):
    return [
        {
            'name': royalty_split.get_user_name(),
            'photo': royalty_split.get_user_profile_photo_url(),
            'rate': float(royalty_split.rate),
        }
        for royalty_split in song.royalty_splits.filter(
            status=RoyaltySplit.STATUS_ACTIVE
        )
    ]


def get_split_start_date(split, release):
    if split.start_date:
        return split.start_date
    elif release.original_release_date:
        return release.original_release_date
    else:
        return release.created


def filter_invite_sensitive_data(invite):
    FILTERED_PLACEHOLDER = '[Filtered]'
    FILTERED_FIELDS = re.compile('email|phone_number', re.I)

    if isinstance(invite, list):
        return [filter_invite_sensitive_data(d) for d in invite]
    if isinstance(invite, dict):
        invite = dict(invite)
        for key, value in invite.items():
            if isinstance(value, list) or isinstance(value, dict):
                invite[key] = filter_invite_sensitive_data(value)
            if FILTERED_FIELDS.search(key):
                invite[key] = FILTERED_PLACEHOLDER
    return invite


class RoyaltySplitFirstRevisionExistsError(Exception):
    pass
