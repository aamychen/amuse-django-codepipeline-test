from users.models import User
from .profile_photo_helper import ProfilePhotoHelper


class UserUpdateService:
    def update(self, instance: User, validated_data: dict) -> User:
        do_not_update = [
            'apple_signin_id',
            'appsflyer_id',
            'email',
            'facebook_access_token',
            'facebook_id',
            'google_id',
            'google_id_token',
            'impact_click_id',
            'password',
            'phone',
            'royalty_token',
            'song_artist_token',
            'user_artist_role_token',
        ]

        [validated_data.pop(field_name, None) for field_name in do_not_update]

        validated_data[
            'profile_photo'
        ] = ProfilePhotoHelper.create_profile_photo_url_from_uuid(validated_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(update_fields=list(validated_data.keys()))

        return instance
