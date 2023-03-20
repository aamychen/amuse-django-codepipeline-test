from django.core.exceptions import PermissionDenied
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from amuse.api.base.views.exceptions import (
    MissingSongOwnershipError,
    ProPermissionError,
    ReleaseDoesNotExist,
    WrongAPIversionError,
)
from amuse.api.v4.serializers.helpers import (
    get_serialized_royalty_splits,
    get_split_start_date,
    update_royalty_splits,
)
from amuse.api.v4.serializers.royalty_split import RoyaltySplitSerializer
from amuse.mixins import LogMixin
from releases.models import Release, ReleaseArtistRole, RoyaltySplit, Song
from users.models import RoyaltyInvitation, UserArtistRole


@permission_classes([IsAuthenticated])
class UpdateRoyaltySplitsView(LogMixin, generics.GenericAPIView):
    serializer_class = RoyaltySplitSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.request.version == '4':
            raise WrongAPIversionError()
        try:
            self.song = Song.objects.get(id=self.kwargs['song_id'])
            primary_artist = (
                self.song.release.releaseartistrole_set.filter(
                    role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST
                )
                .first()
                .artist
            )  # TODO: fix this once main_primary_artist is live
            if not self.request.user.userartistrole_set.filter(
                artist=primary_artist,
                type__in=[UserArtistRole.ADMIN, UserArtistRole.OWNER],
            ).exists():
                raise
        except:
            raise MissingSongOwnershipError()

    def put(self, request, *args, **kwargs):
        if self.song.has_locked_splits():
            raise ValidationError('Cannot update locked split')

        serializer = self.get_serializer(data=request.data, many=True)

        serializer.is_valid(raise_exception=True)

        update_royalty_splits(self.request.user, self.song, serializer.data)
        royalty_splits = get_serialized_royalty_splits(self.song)

        return Response(royalty_splits)


@permission_classes([IsAuthenticated])
class GetRoyaltySplitsView(LogMixin, ListAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.request.version == '4':
            raise WrongAPIversionError()

    def get_queryset(self):
        return RoyaltySplit.objects.filter(
            Q(song__release__user=self.request.user, rate__lt=1.0)
            | ~Q(song__release__user=self.request.user),
            user=self.request.user,
            status__in=[RoyaltySplit.STATUS_ACTIVE, RoyaltySplit.STATUS_CONFIRMED],
        ).select_related('song', 'song__release', 'song__release__cover_art')

    def list(self, request, *args, **kwargs):
        data = [
            {
                "id": split.id,
                "rate": split.rate,
                "status": split.status,
                "artist_name": ", ".join(
                    [artist.name for artist in split.song.get_primary_artists()]
                ),
                "song_name": split.song.name,
                "song_isrc": split.song.isrc.code,
                "cover_art": split.song.release.cover_art.file.url_800x800,
            }
            for split in self.get_queryset()
        ]

        return Response(data, status=status.HTTP_200_OK)


@permission_classes([IsAuthenticated])
class GetRoyaltySplitsByReleaseIDView(LogMixin, ListAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.request.version == '4':
            raise WrongAPIversionError()

    def get_queryset(self):
        try:
            self.release = Release.objects.get(id=self.kwargs['release_id'])
            release_artist = self.release.main_primary_artist
            allowed = release_artist.users.filter(
                userartistrole__type__in=[
                    UserArtistRole.OWNER,
                    UserArtistRole.ADMIN,
                    UserArtistRole.MEMBER,
                ]
            )
            user = self.request.user
            if user not in allowed:
                raise PermissionDenied
        except Release.DoesNotExist:
            raise ReleaseDoesNotExist

        return (
            RoyaltySplit.objects.filter(song__release=self.release)
            .select_related('song', 'song__release', 'song__release__cover_art')
            .order_by('id')
        )

    def list(self, request, *args, **kwargs):
        data = [
            {
                "split_id": split.id,
                "song_id": split.song.id,
                "user_id": split.user.id if split.user else None,
                "first_name": split.user.first_name if split.user else None,
                "last_name": split.user.last_name if split.user else None,
                "profile_photo": split.user.profile_photo if split.user else None,
                "rate": split.rate,
                "status": split.status,
                "start_date": get_split_start_date(split, self.release),
                "end_date": split.end_date,
                "invites": [
                    {
                        "invite_id": invite.id,
                        "invite_inviter": invite.inviter.id,
                        "invite_invitee_name": invite.name,
                        "invite_invitee": invite.invitee.id if invite.invitee else None,
                        "invite_status": invite.status,
                        "invite_last_sent": invite.last_sent,
                        "invite_updated": invite.updated,
                        "invite_created": invite.created,
                    }
                    for invite in RoyaltyInvitation.objects.filter(royalty_split=split)
                ],
            }
            for split in self.get_queryset()
        ]

        return Response(data, status=status.HTTP_200_OK)
