from django.db import models


class ReleaseTakedownRequest(models.Model):
    REASON_SWITCH_DISTRIBUTOR = "switch_distributor"
    REASON_DISLIKE_RELEASE = "dislike_release"
    REASON_CHANGE_AUDIO = "change_audio"
    REASON_CHANGE_ISRC = "change_isrc"
    REASON_SIGNED_TO_LABEL = "signed_to_label"
    REASON_OTHER = "other"

    TAKEDOWN_REASON_CHOICES = (
        (REASON_SWITCH_DISTRIBUTOR, "Switch distributor"),
        (REASON_DISLIKE_RELEASE, "Dislike release"),
        (REASON_CHANGE_AUDIO, "Changing audio"),
        (REASON_CHANGE_ISRC, "Changing ISRC"),
        (REASON_SIGNED_TO_LABEL, "Signed to label"),
        (REASON_OTHER, "Other"),
    )

    release = models.ForeignKey('releases.Release', on_delete=models.CASCADE)
    takedown_reason = models.CharField(choices=TAKEDOWN_REASON_CHOICES, max_length=32)
    requested_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, editable=False
    )
    requested_at = models.DateTimeField(auto_now_add=True)
