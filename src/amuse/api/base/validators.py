import logging
from urllib.parse import urlparse

import phonenumbers
import requests
from django.conf import settings
from django.contrib.auth.password_validation import MinimumLengthValidator
from django.core import exceptions
from phonenumbers.phonenumberutil import NumberParseException
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueValidator

from amuse.api.base.views.exceptions import WrongAPIversionError
from amuse.settings.constants import MIN_PASSWORD_LENGTH
from amuse.storages import S3Storage
from releases.models import Genre
from releases.models import MetadataLanguage
from users.managers import UserManager
from users.models import ArtistV2

logger = logging.getLogger(__name__)
import re


def validate_cover_art_filename(s3_key):
    # Strip away anything that's not the filename
    s3_key = s3_key.rsplit('/', 1)[-1]
    storage = S3Storage(bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME)
    if not storage.exists(s3_key):
        raise serializers.ValidationError(
            '%s file not found on remote storage.' % s3_key
        )


def validate_audio_s3_key(s3_key):
    storage = S3Storage(bucket_name=settings.AWS_SONG_FILE_UPLOADED_BUCKET_NAME)
    if not storage.exists(s3_key):
        raise serializers.ValidationError(
            '%s file not found on remote storage.' % s3_key
        )


def validate_genre(genre):
    genre = Genre.objects.filter(pk=genre['id']).first()
    if not genre:
        raise serializers.ValidationError(f'Invalid genre ID')
    if genre.status is not Genre.STATUS_ACTIVE:
        raise serializers.ValidationError(
            f"Genre '{genre}' is unfortunately deprecated. Please pick another"
            " or contact customer support."
        )


def validate_audio_url(url):
    # Make sure URL ends with a filename in a supported format
    parsed_url = urlparse(url)
    if not parsed_url.path.split('.')[-1].lower() in ['wav', 'flac']:
        raise serializers.ValidationError('Filename needs to end with .wav or .flac')

    # Make sure URL returns a valid status code
    try:
        res = requests.head(url, allow_redirects=True)
    except Exception:
        logger.exception('Error validating audio url')
        raise serializers.ValidationError('Error validating audio URL')
    if res.status_code != 200:
        raise serializers.ValidationError(
            'URL responded with code %s' % res.status_code
        )

    # Make sure file is in a supported format
    content_type = res.headers['Content-Type']
    logger.info('Dropbox content type %s for url %s' % (content_type, url))

    if content_type not in ['audio/x-wav', 'audio/flac', 'application/json']:
        raise serializers.ValidationError(
            'Invalid content type: "%s", on URL: "%s"' % (content_type, url)
        )


def validate_royalty_split_total(contributors):
    total = sum([c.get('royalty_split', 0) for c in contributors])
    if total not in [0, 100]:
        raise serializers.ValidationError(
            f'contributor royalty_split adds up to {total}. ' 'Should be 0 or 100.'
        )


def validate_royalty_split_target(contributor):
    if contributor.get('royalty_split') and not (
        contributor.get('email') or contributor.get('user_id')
    ):
        raise serializers.ValidationError(
            '(email or user_id) is required when royalty_split is used'
        )


def validate_language(fuga_code: str):
    if not MetadataLanguage.by_code(fuga_code):
        raise serializers.ValidationError(f'Invalid language')
    return fuga_code


class EmailUniqueValidator(UniqueValidator):
    def __call__(self, email, *args, **kwargs):
        normalized_email = UserManager.normalize_email(email)
        super().__call__(normalized_email, *args, **kwargs)


def validate_no_duplicates(contributors):
    seen = set()
    for data in contributors:
        artist = data.get('artist')
        name = artist.get('name')
        sanitized_name = re.sub(' +', ' ', name).strip()
        t = tuple((sanitized_name, data.get('role')))
        if t in seen:
            raise serializers.ValidationError(
                'Invalid contributors data submitted. Duplicate (name, role) submitted.'
            )
        seen.add(t)


def validate_artist_name(validated_data):
    if validated_data.get('artist_name', None) == '':
        raise serializers.ValidationError(
            {'artist_name': ['This field may not be blank.']}
        )


def validate_artist_spotify_id(value):
    if value:
        is_claimed = ArtistV2.objects.filter(
            spotify_id=value, owner__isnull=False
        ).exists()
        if is_claimed:
            raise serializers.ValidationError(
                'Artist with this spotify already exists.'
            )


def validate_phone_number(value):
    """
    Validates phone number which is provided as a string.

    In case None was provided the same value will be returned.

        Args:
        ----
            value (str or None): Phone number as a string or None if it was
                not specified.

        Returns:
        -------
            value (str or None): The same as the input if the value is valid or
                None.

        Raises:
        ------
            ValidationError: Only raised when the value in different than None
                and invalid phone number.
    """
    if value is not None:
        try:
            parsed_phone = phonenumbers.parse(value)

            if not phonenumbers.is_valid_number(parsed_phone):
                raise serializers.ValidationError('Enter a valid phone number.')
        except NumberParseException:
            raise serializers.ValidationError('Enter a valid phone number.')

    return value


def validate_not_owner_email(user, email):
    if not user or not user.email:
        return

    if not email:
        return

    if user.email.lower() == email.lower():
        raise serializers.ValidationError('Cannot use your own email address.')


def validate_primary_artist_on_song(songs):
    for song in songs:
        primary_artist_found = False
        artists_roles_list = song['artists_roles']
        for artist_role in artists_roles_list:
            role_list = artist_role['roles']
            if 'primary_artist' in role_list:
                primary_artist_found = True
        if not primary_artist_found:
            raise serializers.ValidationError('Song must have primary_artist role')

    return songs


def validate_no_duplicate_isrc(songs):
    isrcs = [song['isrc'] for song in songs if 'isrc' in song.keys() and song['isrc']]

    if len(isrcs) != len(set(isrcs)):
        raise serializers.ValidationError('Duplicate ISRC')

    return songs


def validate_tiktok_name(value, error=exceptions.ValidationError):
    if value is None:
        return None
    if not isinstance(value, str):
        raise error('Tiktok handle is not of string type format')
    value = value.strip()
    if len(value) < 2:
        raise error('Tiktok handle provided is too short')
    if len(value) > 24:
        raise error('Tiktok handle is too long')
    if not re.match(r"^[\w.]{2,24}$", value):
        raise error('Invalid tiktok handle')
    return value


def validate_allow_max_one_field_with_value(obj: dict, fields: []):
    fields_with_value = [field for field in fields if obj.get(field, None) is not None]

    if len(fields_with_value) <= 1:
        return

    msg = ', '.join(fields_with_value)
    raise ValidationError(
        {
            field: f'Only one of the fields can be set simultaneously. Fields: {msg}.'
            for field in fields_with_value
        }
    )


def validate_digits_input(argument_value: str, argument_name: str = "input_value"):
    if not re.match("[+]?\d+$", argument_value):
        raise ValidationError({argument_name: "Input value is invalid"})


def validate_user_password(validated_data: dict):
    """
    Validates password only if social id login is not in request
    """
    social_login_ids = ['google_id_token', 'apple_signin_id', 'facebook_access_token']
    validate_password = True
    for social_id in social_login_ids:
        validate_password &= not validated_data.get(social_id)

    if validate_password:
        MinimumLengthValidator(min_length=MIN_PASSWORD_LENGTH).validate(
            validated_data['password'] or ''
        )


def validate_social_login_request_version(request):
    """
    1 - not allowed, not used.
    3 - not allowed, not used.
    4 - not allowed, not used.

    2 - used by android app (backward compatibility)
    5 - used by web app (backward compatibility)
    6 - used by ios app (backward compatibility)
    7 - used by "cookie" login
    """
    allowed_list = ['2', '5', '6', '7']
    if request.version not in allowed_list:
        raise WrongAPIversionError()
