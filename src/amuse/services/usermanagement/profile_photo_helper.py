import logging
import re

from app.util import migrate_user_profile_photo_to_s3, user_profile_photo_s3_url

UUID_REGEX = re.compile(r'^\w{8}-\w{4}-\w{4}-\w{4}-\w{12}.*?$')

logger = logging.getLogger(__name__)


class ProfilePhotoHelper:
    @classmethod
    def _has_profile_photo(cls, validated_data: dict) -> bool:
        return 'profile_photo' in validated_data

    @classmethod
    def create_profile_photo_url(cls, validated_data: dict):
        if not cls._has_profile_photo(validated_data):
            return None

        if str(validated_data['profile_photo']).startswith('http'):
            try:
                url = migrate_user_profile_photo_to_s3(validated_data['profile_photo'])
                return url
            except Exception as err:
                logger.warning(
                    f'Unable to migrate user profile photo to s3: {str(err)}'
                )
                return None

        return cls.create_profile_photo_url_from_uuid(validated_data)

    @classmethod
    def create_profile_photo_url_from_uuid(cls, validated_data: dict):
        if not cls._has_profile_photo(validated_data):
            return None

        if bool(UUID_REGEX.match(str(validated_data['profile_photo']))):
            url = user_profile_photo_s3_url(validated_data['profile_photo'])
            return url

        return None
