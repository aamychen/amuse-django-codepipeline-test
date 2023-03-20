from django.db import models
from amuse.db.helpers import dict_to_choices
from releases.models.release import Release
from users.models.user import User


class SupportRelease(models.Model):
    assignee = models.ForeignKey(User, on_delete=models.CASCADE)
    release = models.OneToOneField(Release, on_delete=models.CASCADE)
    prepared = models.BooleanField(default=False)
    date_cated = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)


class SupportEvent(models.Model):
    ASSIGNED = 1
    PREPARED = 2
    APPROVED = 3
    REJECTED = 4

    EVENTS = {
        ASSIGNED: 'assigned',
        PREPARED: 'prepared',
        APPROVED: 'approved',
        REJECTED: 'rejected',
    }

    event = models.PositiveSmallIntegerField(choices=dict_to_choices(EVENTS))
    release = models.ForeignKey(Release, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
