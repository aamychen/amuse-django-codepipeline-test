from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from releases.models import RoyaltySplit
from users.models import UserArtistRole, User


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def related_users(request):
    if request.version == '4':
        user_id = request.user.id

        # Users that our user has given royalty splits to
        user_ids_related_by_royaltysplits = (
            RoyaltySplit.objects.filter(song__release__user__exact=user_id)
            .distinct()
            .values_list("user", flat=True)
            .exclude(user__id=user_id)
        )

        # Get the user's artists
        artist_id_list = UserArtistRole.objects.filter(user_id=user_id).values_list(
            "artist", flat=True
        )

        users_related_by_royaltysplits = (
            User.objects.filter(id__in=list(user_ids_related_by_royaltysplits))
            .exclude(id=user_id)
            .values("id", "first_name", "last_name", "profile_photo")
        )

        users_related_by_artist = (
            User.objects.filter(artists__in=list(artist_id_list))
            .exclude(id=user_id)
            .values("id", "first_name", "last_name", "profile_photo")
        )

        all_related_users = users_related_by_artist.union(
            users_related_by_royaltysplits
        )

        # Build the final payload
        response_payload = [
            {
                "id": user["id"],
                "name": "%s %s" % (user["first_name"], user["last_name"]),
                "profile_photo": user["profile_photo"],
            }
            for user in all_related_users
        ]

        return Response(response_payload, status=status.HTTP_200_OK)

    return Response(status=status.HTTP_400_BAD_REQUEST)
