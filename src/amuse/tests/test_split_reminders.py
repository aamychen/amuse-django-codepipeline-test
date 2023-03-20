from decimal import Decimal
from datetime import datetime, timedelta
from users.models import RoyaltyInvitation
from releases.models import Release
from amuse.tests.test_api.base import AmuseAPITestCase
from users.tests.factories import UserFactory, RoyaltyInvitationFactory
from releases.tests.factories import ReleaseFactory, SongFactory, RoyaltySplitFactory
from releases.splits_reminders import (
    send_split_day_before_release,
    send_split_not_accepted_3_days,
)


class TestSplitNotAcceptedDayBeforeRelease(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.release = ReleaseFactory(
            release_date=datetime.now() + timedelta(days=1),
            status=Release.STATUS_APPROVED,
        )
        self.song = SongFactory(release=self.release)
        self.split = RoyaltySplitFactory(song=self.song, user=None, rate=Decimal("0.3"))
        self.split_invite = RoyaltyInvitationFactory(
            inviter=self.user,
            royalty_split=self.split,
            status=RoyaltyInvitation.STATUS_PENDING,
        )

    def test_send_split_not_accepted_day_before_release(self):
        data = send_split_day_before_release(is_test=True)
        self.assertTrue(len(data), 1)


class TestSplitNotAccept3Day(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.release = ReleaseFactory(status=Release.STATUS_APPROVED)
        self.song = SongFactory(release=self.release)
        self.split = RoyaltySplitFactory(song=self.song, user=None, rate=Decimal("0.3"))
        self.split_invite = RoyaltyInvitationFactory(
            inviter=self.user,
            royalty_split=self.split,
            status=RoyaltyInvitation.STATUS_PENDING,
        )

        self.split_invite.created = datetime.now() - timedelta(days=3)
        self.split_invite.save()

    def test_send_split_not_accepted_3_days(self):
        data = send_split_not_accepted_3_days(is_test=True)
        self.assertTrue(len(data), 1)
