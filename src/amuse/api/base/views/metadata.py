from pyslayer.exceptions import SlayerRequestError
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from slayer.clientwrapper import metadata_spotifyartist, spotify_artist_lookup


@api_view(["POST"])
@permission_classes([AllowAny])
def artist(request):
    if "query" not in request.data or not request.data["query"]:
        return JsonResponse({}, status=status.HTTP_400_BAD_REQUEST)
    try:
        response = metadata_spotifyartist(request.data["query"])
    except SlayerRequestError:
        response = None

    return JsonResponse(response or {}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def artist_by_spotify_id(_, spotify_id):
    try:
        response = spotify_artist_lookup(spotify_id)
    except SlayerRequestError:
        response = None

    return JsonResponse(response or {}, status=status.HTTP_200_OK)
