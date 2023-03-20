import logging

from django.core.cache import cache
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from pyslayer.exceptions import SlayerRequestError, SlayerMemberResolutionError
from pyslayer.utils import to_http1_error

from slayer.clientwrapper import user_activity, artist_activity


log = logging.getLogger(__name__)


CACHE_FOR_HOURS = 1


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def activity(request, user_id, path):
    if request.user.id != user_id:
        return JsonResponse({}, status=status.HTTP_401_UNAUTHORIZED)

    cache_key = f"user_{user_id}_path_{path}"
    response = cache.get(cache_key)
    if response is None:
        try:
            response = user_activity(request.user.id, path, request.GET)
        except SlayerMemberResolutionError as err:
            log.warning(err)
            return JsonResponse({}, status=404)
        except SlayerRequestError as err:
            http1_error = to_http1_error(err.status)
            return JsonResponse({}, status=http1_error)

        cache.set(cache_key, response, 60 * 60 * CACHE_FOR_HOURS)
    return JsonResponse(cache.get(cache_key, {}), status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def artist(request, artist_id, endpoint):
    if not request.user.artists.filter(pk=artist_id).exists():
        return JsonResponse({}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        response = artist_activity(artist_id, endpoint)
    except SlayerMemberResolutionError as err:
        log.warning(err)
        return JsonResponse({}, status=404)
    except SlayerRequestError as err:
        http1_error = to_http1_error(err.status)
        return JsonResponse({}, status=http1_error)

    return JsonResponse(response or {}, status=200)
