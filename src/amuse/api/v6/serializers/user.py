import logging

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from amuse.api.base.validators import (
    EmailUniqueValidator,
    validate_artist_spotify_id,
    validate_allow_max_one_field_with_value,
    validate_user_password,
)
from amuse.services.usermanagement import RegistrationService, UserUpdateService
from amuse.vendor.twilio.sms import validate_phone
from users.models import User

logger = logging.getLogger(__name__)


class UserSerializer(serializers.Serializer):
    facebook_access_token = serializers.CharField(
        write_only=True, required=False, default=None, allow_null=True, allow_blank=True
    )
    facebook_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    firebase_token = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    google_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    google_id_token = serializers.CharField(
        write_only=True, required=False, default=None, allow_null=True, allow_blank=True
    )
    profile_link = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    profile_photo = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    otp_enabled = serializers.BooleanField(read_only=True, default=False)
    phone_verified = serializers.BooleanField(read_only=True, default=False)
    phone = serializers.CharField(required=True)
    tier = serializers.IntegerField(read_only=True, default=0)
    is_free_trial_active = serializers.BooleanField(read_only=True, default=False)
    is_free_trial_eligible = serializers.BooleanField(default=False, read_only=True)
    is_frozen = serializers.BooleanField(read_only=True)
    is_fraud_attempted = serializers.BooleanField(read_only=True, default=False)
    impact_click_id = serializers.CharField(
        write_only=True, allow_null=True, allow_blank=True, required=False
    )
    payee_profile_exist = serializers.BooleanField(read_only=True)

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
    country = serializers.CharField(min_length=2, max_length=2)
    language = serializers.CharField(
        min_length=2, max_length=2, allow_null=True, allow_blank=True
    )
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
    spotify_id = serializers.CharField(
        validators=[validate_artist_spotify_id],
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    newsletter = serializers.BooleanField(default=False)

    # write only fields
    password = serializers.CharField(write_only=True, allow_null=True)
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
        if self.instance:
            # do not validate if not POST
            return super().validate(attrs)

        validate_allow_max_one_field_with_value(
            attrs, ['royalty_token', 'user_artist_role_token', 'song_artist_token']
        )

        attrs['phone'] = validate_phone(attrs.get('phone'))

        validate_user_password(attrs)

        return super().validate(attrs)

    def create(self, validated_data):
        user = RegistrationService().create_user(
            self.context.get('request'), validated_data
        )
        return user

    def update(self, instance, validated_data):
        return UserUpdateService().update(instance, validated_data)
