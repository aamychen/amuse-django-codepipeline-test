from amuse.throttling import RestrictedEndpointThrottle
from django.core import exceptions
from django.core.validators import validate_email
from amuse.api.base.validators import validate_phone_number
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework import permissions, status
from rest_framework.response import Response
from users.managers import UserManager
from users.models import User
from .genre import GenreListViewSet
from .release import ReleaseViewSet
from .song_file_upload import (
    SongFileUploadViewSet,
    LinkSongFileDownloadViewSet,
    GoogleDriveSongFileDownloadViewSet,
)
from .country import CountryViewSet
from .user import UserViewSet
from .artist import ArtistViewSet
from .team_invitation import TeamInvitationViewSet
from .royalty_invitation import RoyaltyInvitationViewSet
from .subscription import SubscriptionViewSet
from .team_user_roles import TeamUserRolesViewSet
from .metadata_language import MetadataLanguageViewSet


@api_view(['POST', 'GET'])
@permission_classes([permissions.AllowAny])
@throttle_classes([RestrictedEndpointThrottle])
def check_email(request):
    try:
        email = request.data.get('email')
        validate_email(email)
        normalized_email = UserManager.normalize_email(email)
        user = User.objects.filter(email=normalized_email).first()
        if user:
            data = {'facebook': bool(user.facebook_id), 'google': bool(user.google_id)}
            return Response(status=status.HTTP_200_OK, data=data)
    except (exceptions.ValidationError, User.DoesNotExist):
        pass
    return Response(status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([RestrictedEndpointThrottle])
def check_email_exists(request):
    try:
        email = request.data.get('email', None)
        validate_email(email)
        exists = User.objects.filter(email=UserManager.normalize_email(email)).exists()
        data = {'exists': exists}
        return Response(status=status.HTTP_200_OK, data=data)

    except Exception:
        pass
    return Response(
        status=status.HTTP_400_BAD_REQUEST, data={"message": "Invalid email."}
    )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([RestrictedEndpointThrottle])
def check_phone_exists(request):
    try:
        phome = request.data.get('phone_number', None)
        validated_phone = validate_phone_number(phome)
        exists = User.objects.filter(phone=validated_phone).exists()
        data = {'exists': exists}
        return Response(status=status.HTTP_200_OK, data=data)
    except Exception:
        pass
    return Response(
        status=status.HTTP_400_BAD_REQUEST, data={"message": "Invalid phone number."}
    )
