from amuse.db.decorators import with_history
from releases.models import Release, Song


@with_history
class GenericRelease(Release):
    class Meta:
        proxy = True


@with_history
class PendingRelease(Release):
    class Meta:
        proxy = True


@with_history
class ApprovedRelease(Release):
    class Meta:
        proxy = True


@with_history
class DeliveredRelease(Release):
    class Meta:
        proxy = True


@with_history
class NotApprovedRelease(Release):
    class Meta:
        proxy = True


@with_history
class RejectedRelease(Release):
    class Meta:
        proxy = True


class AssignedPendingRelease(Release):
    class Meta:
        proxy = True


class AssignedPreparedRelease(Release):
    class Meta:
        proxy = True


class ProRelease(Release):
    class Meta:
        proxy = True


class FreeRelease(Release):
    class Meta:
        proxy = True


class PlusRelease(Release):
    class Meta:
        proxy = True
