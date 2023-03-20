from django.db import models

from users.models.user import User
from releases.models.release import Release


class MinfraudResult(models.Model):
    # Local event types (don't use them in a request to minFraud)
    EVENT_DEFAULT = 0
    EVENT_ACCOUNT_CREATION = 1
    EVENT_RELEASE = 2
    EVENT_EMAIL_CHANGE = 3
    EVENT_PASSWORD_RESET = 4

    EVENT_CHOICES = (
        (EVENT_DEFAULT, 'Default'),
        (EVENT_ACCOUNT_CREATION, 'Account creation'),
        (EVENT_RELEASE, 'Release'),
        (EVENT_EMAIL_CHANGE, 'Email change'),
        (EVENT_PASSWORD_RESET, 'Password reset'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    release = models.ForeignKey(
        Release, on_delete=models.CASCADE, null=True, blank=True
    )
    response_body = models.TextField()
    fraud_score = models.DecimalField(max_digits=5, decimal_places=2)
    event_time = models.DateTimeField()
    event_type = models.PositiveSmallIntegerField(
        default=EVENT_DEFAULT, choices=EVENT_CHOICES
    )
