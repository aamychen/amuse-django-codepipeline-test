import json
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.forms.models import model_to_dict
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from amuse import mixins as logmixins
from amuse.analytics import split_accepted
from amuse.api.v4.serializers.helpers import update_splits_state
from releases.models import RoyaltySplit
from users.models import RoyaltyInvitation


logger = logging.getLogger(__name__)


class RoyaltyInvitationViewSet(logmixins.LogMixin, viewsets.GenericViewSet):
    permission_classes = (permissions.AllowAny,)
    queryset = RoyaltyInvitation.objects.all()

    @action(
        methods=['POST'],
        detail=False,
        url_path='confirm',
        url_name='confirm',
        permission_classes=(permissions.IsAuthenticated,),
    )
    @transaction.atomic
    def confirm(self, request):
        token = request.data.get('token')

        if token is None:
            raise ValidationError({'token': 'missing royalty invitation token'})

        user = request.user
        invite = RoyaltyInvitation.objects.filter(token=token).first()
        if invite is None:
            logger.warning(f'Royalty invite token: "{token}" does not exist')
            raise NotFound()

        if not invite.valid:
            raise ValidationError("invalid token")

        invite.status = RoyaltyInvitation.STATUS_ACCEPTED
        invite.invitee = user
        invite.save()

        split = invite.royalty_split

        split.status = RoyaltySplit.STATUS_CONFIRMED
        split.user = user

        same_user_splits = RoyaltySplit.objects.filter(
            song=split.song, user=user, revision=split.revision
        ).exclude(id=split.id)

        if same_user_splits:
            split.rate += sum([s.rate for s in same_user_splits])
            split_list = [model_to_dict(s) for s in same_user_splits]
            logger.info(
                "Deleted same user splits when accepted invitation %s"
                % json.dumps(split_list, cls=DjangoJSONEncoder)
            )
            same_user_splits.delete()

        owner = split.song.release.main_primary_artist.owner
        split.is_owner = True if user == owner else False
        split.save()

        update_splits_state(split.song, split.revision)

        split_accepted(split)

        logger.info(
            'RoyaltyInvitation accepted, user_id: %s, split_id %s, invitation_id: %s',
            user.pk,
            invite.royalty_split_id,
            invite.pk,
        )

        return Response(status=status.HTTP_202_ACCEPTED)
