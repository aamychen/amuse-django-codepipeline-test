import logging
import re

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueValidator

from amuse.tasks import send_segment_signup_completed_event
from amuse.analytics import split_accepted, sign_up as analytic_sign_up
from amuse.api.base.validators import (
    EmailUniqueValidator,
    validate_artist_name,
    validate_artist_spotify_id,
)
from amuse.api.v4.serializers.helpers import fetch_spotify_image, update_splits_state
from amuse.platform import PlatformHelper
from app.util import migrate_user_profile_photo_to_s3, user_profile_photo_s3_url
from releases.models import RoyaltySplit
from users.models import (
    RoyaltyInvitation,
    SongArtistInvitation,
    TeamInvitation,
    User,
    UserArtistRole,
    UserMetadata,
    AppsflyerDevice,
)
from countries.models import Country

UUID_REGEX = re.compile(r'^\w{8}-\w{4}-\w{4}-\w{4}-\w{12}.*?$')

logger = logging.getLogger(__name__)


def should_create_artist(skip_artist_creation: bool, validated_data: dict):
    if skip_artist_creation:
        return False

    return validated_data.get('artist_name') is not None


class UserSerializer(serializers.Serializer):
    # core fields
    id = serializers.IntegerField(read_only=True)
    auth_token = serializers.CharField(read_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    artist_name = serializers.CharField(
        allow_null=True, allow_blank=True, required=False
    )
    email = serializers.EmailField(
        validators=[
            EmailUniqueValidator(
                queryset=User.objects.all(),
                message='user with this email already exists.',
            )
        ]
    )
    email_verified = serializers.BooleanField(read_only=True)
    category = serializers.CharField(source='get_category_name', read_only=True)
    phone = serializers.CharField()
    country = serializers.CharField(min_length=2, max_length=2)
    language = serializers.CharField(
        min_length=2, max_length=2, allow_null=True, allow_blank=True
    )
    facebook_id = serializers.CharField(allow_null=True, allow_blank=True)
    google_id = serializers.CharField(allow_null=True, allow_blank=True)
    apple_signin_id = serializers.CharField(
        allow_null=True,
        allow_blank=True,
        required=False,
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message='Only one Amuse account allowed per Apple sign-in',
            )
        ],
    )
    profile_link = serializers.CharField(allow_null=True, allow_blank=True)
    profile_photo = serializers.CharField(allow_null=True, allow_blank=True)
    spotify_id = serializers.CharField(
        validators=[validate_artist_spotify_id],
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    spotify_page = serializers.CharField(
        allow_null=True, allow_blank=True, required=False
    )
    spotify_image = serializers.CharField(
        allow_null=True, allow_blank=True, required=False
    )
    twitter_name = serializers.CharField(
        allow_null=True, allow_blank=True, required=False
    )
    facebook_page = serializers.CharField(
        allow_null=True, allow_blank=True, required=False
    )
    instagram_name = serializers.CharField(
        allow_null=True, allow_blank=True, required=False
    )
    soundcloud_page = serializers.CharField(
        allow_null=True, allow_blank=True, required=False
    )
    youtube_channel = serializers.CharField(
        allow_null=True, allow_blank=True, required=False
    )
    firebase_token = serializers.CharField(allow_null=True, allow_blank=True)
    newsletter = serializers.BooleanField(default=False)
    is_pro = serializers.BooleanField(default=False, read_only=True)
    is_eligible_for_free_trial = serializers.BooleanField(
        default=False,
        read_only=True,
        help_text='Obsolete. Use "is_free_trial_eligible" instead.',
    )

    # write only fields
    password = serializers.CharField(write_only=True, allow_null=True)
    facebook_access_token = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True
    )
    google_id_token = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True
    )
    royalty_token = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=False, required=False
    )
    user_artist_role_token = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=False, required=False
    )
    song_artist_token = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=False, required=False
    )
    created = serializers.DateTimeField(read_only=True)
    main_artist_profile = serializers.SerializerMethodField(read_only=True)
    impact_click_id = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True, required=False
    )
    verify_phone = serializers.NullBooleanField(write_only=True, default=False)
    idfa = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True, required=False
    )
    idfv = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True, required=False
    )
    aaid = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True, required=False
    )
    oaid = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True, required=False
    )
    imei = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True, required=False
    )
    appsflyer_id = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True, required=False
    )

    def get_main_artist_profile(self, user):
        return user.main_artist_profile

    def validate(self, attrs):
        validation_counter = 0
        tokens = ['royalty_token', 'user_artist_role_token', 'song_artist_token']
        for token in tokens:
            if attrs.get(token) is not None:
                validation_counter += 1
        if validation_counter > 1:
            raise ValidationError(
                "only one of the following fields can be set at the same time: "
                "[royalty_token, user_artist_role_token, song_artist_token]"
            )

        return attrs

    def _create_user(self, validated_data, skip_artist_creation=False):
        validated_data.pop('facebook_access_token')
        validated_data.pop('google_id_token')
        spotify_image = validated_data.pop('spotify_image', None)
        spotify_id = validated_data.get('spotify_id', None)
        impact_click_id = validated_data.get('impact_click_id', None)
        validated_data.pop("verify_phone", None)

        # Appsflyer device info
        idfa = validated_data.pop('idfa', None)
        idfv = validated_data.pop('idfv', None)
        aaid = validated_data.pop('aaid', None)
        oaid = validated_data.pop('oaid', None)
        imei = validated_data.pop('imei', None)
        appsflyer_id = validated_data.pop('appsflyer_id', None)

        create_artist = should_create_artist(skip_artist_creation, validated_data)

        if 'royalty_token' in validated_data:
            validated_data.pop('royalty_token')

        if 'user_artist_role_token' in validated_data:
            validated_data.pop('user_artist_role_token')

        if 'song_artist_token' in validated_data:
            validated_data.pop('song_artist_token')

        if 'impact_click_id' in validated_data:
            validated_data.pop('impact_click_id')

        if 'profile_photo' in validated_data:
            if str(validated_data['profile_photo']).startswith('http'):
                try:
                    validated_data['profile_photo'] = migrate_user_profile_photo_to_s3(
                        validated_data['profile_photo']
                    )
                except Exception:
                    validated_data['profile_photo'] = None
            elif bool(UUID_REGEX.match(str(validated_data['profile_photo']))):
                validated_data['profile_photo'] = user_profile_photo_s3_url(
                    validated_data['profile_photo']
                )

        email = validated_data.pop('email')
        password = validated_data.pop('password')
        user = User.objects.create_user(email, password, **validated_data)

        if create_artist:
            spotify_image = fetch_spotify_image(spotify_id, spotify_image)
            user.create_artist_v2(
                name=validated_data['artist_name'],
                spotify_page=validated_data.get('spotify_page'),
                twitter_name=validated_data.get('twitter_name'),
                facebook_page=validated_data.get('facebook_page'),
                instagram_name=validated_data.get('instagram_name'),
                soundcloud_page=validated_data.get('soundcloud_page'),
                youtube_channel=validated_data.get('youtube_channel'),
                spotify_id=spotify_id,
                spotify_image=spotify_image,
            )

        if appsflyer_id is not None:
            appsflyer_device_info = {
                'idfa': idfa,
                'idfv': idfv,
                'aaid': aaid,
                'oaid': oaid,
                'imei': imei,
                'appsflyer_id': appsflyer_id,
            }
            self._create_appsflyer_device(appsflyer_device_info, user)

        if impact_click_id is not None:
            UserMetadata.objects.create(user=user, impact_click_id=impact_click_id)

            platform = PlatformHelper.from_request(self.context.get("request"))
            analytic_sign_up(user, platform, impact_click_id)

        return user

    def update(self, instance, validated_data):
        validated_data.pop('email', None)  # Silently drop email to prevent changing.
        validated_data.pop('password', None)
        validated_data.pop('apple_signin_id', None)
        validated_data.pop('google_id', None)
        validated_data.pop('facebook_id', None)
        validated_data.pop("verify_phone", None)

        # Prevent phone number change if otp is not enabled and phone not verified
        if not instance.otp_enabled and not instance.phone_verified:
            validated_data.pop('phone', None)

        if bool(UUID_REGEX.match(str(validated_data['profile_photo']))):
            validated_data['profile_photo'] = user_profile_photo_s3_url(
                validated_data['profile_photo']
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

    def create_user_flow(self, validated_data):
        user = self._create_user(validated_data=validated_data)
        self.send_signup_completed_event(user, "regular")
        return user

    @transaction.atomic
    def confirm_royalty_invitation_flow(self, validated_data, token):
        invite = RoyaltyInvitation.objects.filter(token=token).first()
        if invite is None:
            logger.warning(f'Royalty invite token: "{token}" does not exist')
            raise ValidationError("invalid token")

        if not invite.valid:
            raise ValidationError("invalid token")

        assert invite.invitee is None, 'invitation is created for existing user'

        user = self._create_user(
            validated_data=validated_data, skip_artist_creation=True
        )
        invite.status = RoyaltyInvitation.STATUS_ACCEPTED
        invite.invitee = user
        invite.save()

        invite.royalty_split.status = RoyaltySplit.STATUS_CONFIRMED
        invite.royalty_split.user = user
        invite.royalty_split.save()

        update_splits_state(invite.royalty_split.song, invite.royalty_split.revision)
        self.send_signup_completed_event(user, "invite")
        split_accepted(invite.royalty_split)
        return user

    @transaction.atomic
    def confirm_user_artist_role_invitation_flow(self, validated_data, token):
        invite = TeamInvitation.objects.filter(token=token).first()

        # validate invite
        if invite is None:
            raise ValidationError("invalid token")

        if not invite.valid or invite.invitee is not None:
            raise ValidationError("invalid token")

        user = self._create_user(
            validated_data=validated_data, skip_artist_creation=True
        )

        invite.status = TeamInvitation.STATUS_ACCEPTED
        invite.save()

        user_artist_role = UserArtistRole(
            user=user, artist=invite.artist, type=invite.team_role
        )
        user_artist_role.save()

        self.send_signup_completed_event(user, "invite")

        return user

    @transaction.atomic
    def confirm_song_artist_invitation_flow(self, validated_data, token):
        invite = None
        try:
            invite = SongArtistInvitation.objects.get(token=token)
        except ObjectDoesNotExist:
            logger.error('Invite with token=%s does not exist', token)

        # validate invite
        if invite is None:
            raise ValidationError("invalid token")

        if not invite.valid:
            raise ValidationError("invalid token")

        user = self._create_user(
            validated_data=validated_data, skip_artist_creation=True
        )
        user.userartistrole_set.create(artist=invite.artist, type=UserArtistRole.OWNER)

        invite.status = SongArtistInvitation.STATUS_ACCEPTED
        invite.invitee = user
        invite.save()

        self.send_signup_completed_event(user, "invite")

        return user

    def create(self, validated_data):
        royalty_token = validated_data.get('royalty_token', None)
        if royalty_token is not None:
            return self.confirm_royalty_invitation_flow(validated_data, royalty_token)

        user_artist_role_token = validated_data.get('user_artist_role_token', None)
        if user_artist_role_token is not None:
            return self.confirm_user_artist_role_invitation_flow(
                validated_data, user_artist_role_token
            )

        validate_artist_name(validated_data)
        song_artist_invite_token = validated_data.get('song_artist_token', None)
        if song_artist_invite_token is not None:
            return self.confirm_song_artist_invitation_flow(
                validated_data, song_artist_invite_token
            )

        return self.create_user_flow(validated_data)

    def send_signup_completed_event(self, user, signup_path):
        request = self.context.get("request")
        if not self._should_trigger_segment_event(request):
            return
        platform_name = PlatformHelper.from_request(request).name.lower()
        detected_country_name = self._get_country_name(request)
        send_segment_signup_completed_event.delay(
            user, platform_name, detected_country_name, signup_path
        )

    def _get_country_name(self, request):
        detected_country_name = None
        detected_country_code = request.META.get('HTTP_CF_IPCOUNTRY')
        detected_country = Country.objects.filter(code=detected_country_code).first()
        if detected_country is not None:
            detected_country_name = detected_country.name
        return detected_country_name

    def _should_trigger_segment_event(self, request):
        """HTTP_X_TRIGGER_EVENT - Custom request header which suggest does segment event
        need to be triggered on BE side or not so we don't trigger it twice - on frontend and backend
        ie. to avoid duplicates"""
        if not request:
            return
        return request.META.get('HTTP_X_TRIGGER_EVENT') == '1'

    def _create_appsflyer_device(self, appsflyer_device_info, user):
        AppsflyerDevice.objects.update_or_create(
            appsflyer_id=appsflyer_device_info.get('appsflyer_id'),
            defaults=dict(
                user=user,
                idfa=appsflyer_device_info.get('idfa'),
                idfv=appsflyer_device_info.get('idfv'),
                aaid=appsflyer_device_info.get('aaid'),
                oaid=appsflyer_device_info.get('oaid'),
                imei=appsflyer_device_info.get('imei'),
                updated=timezone.now(),
            ),
        )
