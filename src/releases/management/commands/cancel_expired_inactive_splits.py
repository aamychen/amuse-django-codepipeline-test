import logging
from datetime import datetime, timedelta
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery

from amuse.analytics import split_invites_expired
from releases.models import Release, RoyaltySplit
from users.models import RoyaltyInvitation

logger = logging.getLogger(__name__)

RELEASE_STATUS_LIST = [
    Release.STATUS_DELIVERED,
    Release.STATUS_RELEASED,
    Release.STATUS_TAKEDOWN,
]


def new_job_id():
    return str(uuid4()).replace('-', '')


class InviteInfo:
    def __init__(self, item):
        self.inviter_id = item['inviter_id']
        self.song_name = item['royalty_split__song__name']
        self.revision = item['royalty_split__revision']
        self.song_id = item['royalty_split__song_id']


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "-r",
            "--release_ids",
            type=int,
            nargs="+",
            help="Delete expired inactive royalty invites and splits for "
            "specified release ids. If not set, the command checks all "
            "releases. Example: 744466 671177 831758",
        )

    def handle(self, *args, **kwargs):
        release_ids = kwargs.get('release_ids', None)
        job_id = new_job_id()

        expired_invites = fetch_expired_invite_groups(release_ids)

        for invite in expired_invites:
            splits_for_song_revision = RoyaltySplit.objects.filter(
                song_id=invite.song_id, revision=invite.revision
            ).all()

            splits_deleted_ids = [split.id for split in splits_for_song_revision]

            logger.info(
                f'Expired inactive splits processed: '
                f'job_id={job_id}, '
                f'inviter_id={invite.inviter_id}, '
                f'song_id={invite.song_id}, '
                f'revision={invite.revision}, '
                f'archived_split_ids={splits_deleted_ids}'
            )

            for split in splits_for_song_revision:
                status = dict(RoyaltySplit.STATUS_CHOICES)[split.status]
                logger.info(
                    f'Deleted split details: '
                    f'job_id={job_id}, '
                    f'split_id={split.id}, '
                    f'rate={split.rate:.4f}, '
                    f'status={status}, '
                    f'song_id={split.song_id}, '
                    f'user_id={split.user_id}, '
                    f'revision={split.revision}, '
                    f'is_owner={split.is_owner}, '
                    f'is_locked={split.is_locked}, '
                    f'created={str(split.created)}, '
                    f'start_date={str(split.start_date)}, '
                    f'end_date={str(split.end_date)}.'
                )

            splits_for_song_revision.delete()

            split_invites_expired(user_id=invite.inviter_id, song_name=invite.song_name)


def fetch_expired_invite_groups(release_ids=None):
    expiration_date = datetime.now() - timedelta(days=RoyaltyInvitation.EXPIRATION_DAYS)

    # find LATEST revision for specified song (IGNORE revision=1)
    latest_revision_subquery = Subquery(
        RoyaltySplit.objects.filter(
            revision__gt=1, song_id=OuterRef('royalty_split__song_id')
        )
        .values('revision')
        .distinct()
        .order_by('-revision')[:1]
    )

    filter_kwargs = {
        "status": RoyaltyInvitation.STATUS_PENDING,
        "last_sent__lt": expiration_date,
        "royalty_split__status__in": [
            RoyaltySplit.STATUS_PENDING,
            RoyaltySplit.STATUS_CONFIRMED,
        ],
        "royalty_split__revision": latest_revision_subquery,
        "royalty_split__song__release__status__in": RELEASE_STATUS_LIST,
    }

    if release_ids is not None:
        filter_kwargs['royalty_split__song__release_id__in'] = release_ids

    invites_raw = list(
        RoyaltyInvitation.objects.filter(**filter_kwargs)
        .select_related(
            'royalty_split', 'royalty_split__song', 'royalty_split__song__release'
        )
        .values(
            'inviter_id',
            'royalty_split__song__name',
            'royalty_split__song_id',
            'royalty_split__revision',
        )
        .distinct()
    )

    invites = [InviteInfo(item) for item in invites_raw]

    return invites
