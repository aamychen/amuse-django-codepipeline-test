import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.request import Request

from amuse.analytics import sign_up as analytic_sign_up
from amuse.api.v4.serializers.helpers import fetch_spotify_image
from amuse.platform import PlatformHelper
from users.models import User, UserMetadata, AppsflyerDevice
from .profile_photo_helper import ProfilePhotoHelper
from .signup_flows import SignupFlowFactory

logger = logging.getLogger(__name__)


class RegistrationService:
    @transaction.atomic
    def create_user(self, request: Request, validated_data: dict) -> User:
        signup_flow = SignupFlowFactory.create_flow(validated_data)

        signup_flow.pre_registration(validated_data)
        user = self._create_user(
            request, validated_data, signup_flow.skip_artist_creation
        )
        signup_flow.post_registration(request, user, validated_data)

        return user

    def _create_user(
        self, request: Request, validated_data: dict, skip_artist_creation: bool
    ) -> User:
        # remove non-user fields
        non_user_fields = [
            'facebook_access_token',
            'google_id_token',
            'royalty_token',
            'user_artist_role_token',
            'song_artist_token',
            'verify_phone',
            'impact_click_id',
            'idfa',
            'idfv',
            'aaid',
            'oaid',
            'imei',
            'appsflyer_id',
        ]
        validated_non_user_data = {
            item: validated_data.pop(item, None) for item in non_user_fields
        }

        validated_data['profile_photo'] = ProfilePhotoHelper.create_profile_photo_url(
            validated_data
        )

        # enable OTP for new users
        validated_data['otp_enabled'] = True

        # create user
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        user = User.objects.create_user(email, password, **validated_data)

        self._create_artist_if_required(user, validated_data, skip_artist_creation)
        self._create_appsflyer_device_if_required(user, validated_non_user_data)
        self._create_usermetadata_if_required(
            request, user, validated_non_user_data['impact_click_id']
        )

        return user

    def _create_usermetadata_if_required(self, request, user, impact_click_id):
        if impact_click_id is not None:
            UserMetadata.objects.create(user=user, impact_click_id=impact_click_id)

            platform = PlatformHelper.from_request(request)
            analytic_sign_up(user, platform, impact_click_id)

    def _create_artist_if_required(self, user, validated_data, skip_artist_creation):
        spotify_image = validated_data.get('spotify_image', None)
        spotify_id = validated_data.get('spotify_id', None)

        if skip_artist_creation:
            return False

        if validated_data.get('artist_name', None) is None:
            return

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

    def _create_appsflyer_device_if_required(self, user, validated_non_user_data):
        appsflyer_id = validated_non_user_data.pop('appsflyer_id', None)

        if appsflyer_id is not None:
            AppsflyerDevice.objects.update_or_create(
                appsflyer_id=appsflyer_id,
                defaults=dict(
                    user=user,
                    idfa=validated_non_user_data.get('idfa', None),
                    idfv=validated_non_user_data.get('idfv', None),
                    aaid=validated_non_user_data.get('aaid', None),
                    oaid=validated_non_user_data.get('oaid', None),
                    imei=validated_non_user_data.get('imei', None),
                    updated=timezone.now(),
                ),
            )
