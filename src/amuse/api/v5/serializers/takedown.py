import logging

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from amuse.api.base.mixins import ArtistAuthorizationMixin
from amuse.models.release_takedown_request import ReleaseTakedownRequest

logger = logging.getLogger(__name__)


class TakedownSerializer(serializers.Serializer, ArtistAuthorizationMixin):
    takedown_reason = serializers.ChoiceField(
        choices=ReleaseTakedownRequest.TAKEDOWN_REASON_CHOICES
    )

    def validate(self, data):
        data = super().validate(data)

        user = self.context['user']
        release = self.context['release']

        if not user.is_staff:
            # Check user has permission to take it down (Owner, Admin or SuperAdmin)
            self.get_authorized_artist(release.main_primary_artist.id, user.pk)

        return data
