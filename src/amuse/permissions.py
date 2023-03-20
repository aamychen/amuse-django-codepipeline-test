from django.conf import settings
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.validators import ValidationError

from amuse.api.base.views.exceptions import SubscriptionProviderMismatchError
from amuse.utils import get_client_captcha_token, get_ip_address
from amuse.vendor.google import captcha
from releases.models import ReleaseArtistRole
from subscriptions.models import Subscription, SubscriptionPlan
from users.models import UserArtistRole


class FrozenUserPermission(BasePermission):
    message = 'User is frozen'

    def has_permission(self, request, view):
        if not request.user:
            return False

        return not request.user.is_frozen


class CanManageAdyenSubscription(BasePermission):
    def has_permission(self, request, view):
        subscription = request.user.current_subscription()
        if not subscription:
            return True

        if subscription.provider != Subscription.PROVIDER_ADYEN:
            raise SubscriptionProviderMismatchError()

        return True


class CanDeleteAdyenSubscription(BasePermission):
    def has_permission(self, request, view):
        if request.method != 'DELETE':
            return True

        if request.version == '4':
            subscription = request.user.current_subscription()
        else:
            subscription = request.user.current_entitled_subscription()

        if not subscription:
            return True

        if subscription.provider != Subscription.PROVIDER_ADYEN:
            raise SubscriptionProviderMismatchError()

        return True


class IsOwnerPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


class CanManageArtistPermission(BasePermission):
    """
    Allow artist creation for user that is PRO or does not have an artist
    Allow artists management to users that have OWNER or ADMIN role in artist team
    """

    def has_permission(self, request, view):
        try:
            if view.action == 'create':
                user = request.user
                return (
                    user.tier == SubscriptionPlan.TIER_PRO
                    or not user.userartistrole_set.exists()
                )
            return True
        except:
            return False

    def has_object_permission(self, request, view, artist):
        if request.method in SAFE_METHODS:
            return True
        can_edit = artist.userartistrole_set.filter(
            user=request.user, type__in=[UserArtistRole.ADMIN, UserArtistRole.OWNER]
        ).exists()
        return can_edit


class CanManageArtistSoMeDataPermission(BasePermission):
    def has_object_permission(self, request, view, artist):
        return artist.userartistrole_set.filter(
            user=request.user,
            type__in=[
                UserArtistRole.ADMIN,
                UserArtistRole.OWNER,
                UserArtistRole.MEMBER,
            ],
        ).exists()


class CanManageTeamInvitationsPermission(BasePermission):
    """
    Only PRO user with OWNER and ADMIN roles can create, edit and cancel existing invites
    """

    def has_permission(self, request, view):
        if view.action in ['create', 'update', 'destroy', 'partial_update']:
            user = request.user
            return user.tier == SubscriptionPlan.TIER_PRO
        return True

    def has_object_permission(self, request, view, obj):
        try:
            user = request.user
            artist = obj.artist

            if request.method in SAFE_METHODS:
                return True
            is_admin = UserArtistRole.objects.filter(
                user=user,
                artist=artist,
                type__in=[UserArtistRole.ADMIN, UserArtistRole.OWNER],
            ).exists()
            return is_admin
        except:
            return False


class CanManageTeamRolesPermission(BasePermission):
    """
    Allow artist role management to users that have OWNER or ADMIN role in artist team

    OWNER role cannot be changed or removed

    User can remove himself from the team (ADMIN, MEMBER, SPECTATOR)
    """

    def has_permission(self, request, view):
        if view.action in ['create', 'update', 'partial_update']:
            user = request.user
            return user.tier == SubscriptionPlan.TIER_PRO
        return True

    def has_object_permission(self, request, view, user_artist_role):
        # Allow view only for team members
        if request.method in SAFE_METHODS:
            return UserArtistRole.objects.filter(
                user=request.user, artist=user_artist_role.artist
            ).exists()

        # Owner cannot be changed
        if user_artist_role.type == UserArtistRole.OWNER:
            return False

        # Allow removing self from artist team
        if view.action == 'destroy' and user_artist_role.user == request.user:
            return True

        # Allow managment for owners and admins
        return (
            UserArtistRole.objects.filter(
                user=request.user,
                artist=user_artist_role.artist,
                type__in=[UserArtistRole.ADMIN, UserArtistRole.OWNER],
            ).exists()
            and request.user.tier == SubscriptionPlan.TIER_PRO
        )


class CanUpdateToTeamRolePermission(BasePermission):
    """
    Team users have no permission to upgrade role to OWNER or SUPERADMIN
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        role_type = request.data.get('type')
        type_choices = dict(UserArtistRole.TYPE_CHOICES)
        if role_type in [
            type_choices[UserArtistRole.OWNER],
            type_choices[UserArtistRole.SUPERADMIN],
        ]:
            return False

        return True


class CanCreateReleasesPermission(BasePermission):
    """
    Release creation rules
    """

    MANAGE_ROLES = [UserArtistRole.ADMIN, UserArtistRole.OWNER, UserArtistRole.MEMBER]

    def has_permission(self, request, view):
        try:
            user = request.user
            artist_id = int(request.data.get('artist_id'))

            if user.tier == SubscriptionPlan.TIER_PRO:
                return user.userartistrole_set.filter(
                    artist_id=artist_id, type__in=self.MANAGE_ROLES
                ).exists()

            if user.main_artist_profile:
                return user.main_artist_profile == artist_id

            if user.userartistrole_set.count() == 1:
                return user.userartistrole_set.first().artist_id == artist_id

            return False
        except:
            return False


class CanManageReleasesPermission(BasePermission):
    """
    Allow Release management only to Users that have MANAGE_ROLES on Primary Artist.
    """

    MANAGE_ROLES = [UserArtistRole.ADMIN, UserArtistRole.OWNER, UserArtistRole.MEMBER]

    def has_object_permission(self, request, view, release):
        try:
            user = request.user
            primary_artists = release.releaseartistrole_set.filter(
                role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST, main_primary_artist=True
            ).values('artist')
            return user.userartistrole_set.filter(
                artist__in=primary_artists, type__in=self.MANAGE_ROLES
            ).exists()
        except:
            return False


class CanDeleteReleasesPermission(BasePermission):
    """
    Allow Release deletion only to ADMIN and OWNER roles.
    """

    DELETE_ROLES = [UserArtistRole.ADMIN, UserArtistRole.OWNER]

    def has_object_permission(self, request, view, release):
        try:
            user = request.user
            primary_artists = release.releaseartistrole_set.filter(
                role=ReleaseArtistRole.ROLE_PRIMARY_ARTIST, main_primary_artist=True
            ).values('artist')
            return user.userartistrole_set.filter(
                artist__in=primary_artists, type__in=self.DELETE_ROLES
            ).exists()
        except:
            return False


class ReCaptchaPermission(BasePermission):
    def has_permission(self, request, view):
        if not settings.GOOGLE_CAPTCHA_ENABLED:
            return True

        captcha_client_token = get_client_captcha_token(request)
        if not captcha_client_token:
            raise ValidationError({"request": "Invalid request"})

        ip_address = get_ip_address(request)
        if not captcha.is_human(captcha_client_token, ip_address):
            raise ValidationError({"request": "Invalid request"})

        return True
