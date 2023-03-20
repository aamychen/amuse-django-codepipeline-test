from django.test import TestCase
import pytest
from unittest.mock import patch
from uuid import uuid4

from amuse.services.usermanagement.profile_photo_helper import ProfilePhotoHelper


@pytest.mark.parametrize(
    'validated_data,expected', [({}, False), ({'profile_photo': '123'}, True)]
)
def test_test_has_profile_photo(validated_data, expected):
    actual = ProfilePhotoHelper._has_profile_photo(validated_data)
    assert actual == expected


class TestProfilePhotoHelper(TestCase):
    def test_create_profile_photo_url_if_profile_photo_does_not_exist(self):
        data = {}
        actual = ProfilePhotoHelper.create_profile_photo_url(data)

        self.assertIsNone(actual)

    @patch(
        'amuse.services.usermanagement.profile_photo_helper.migrate_user_profile_photo_to_s3',
        return_value='https://photo.url.s3.com',
    )
    def test_create_profile_photo_url_if_profile_photo_starts_with_http(
        self, mock_migrate_user_profile_photo_to_s3
    ):
        input_url = 'https://fake.url.com/photo.jpeg'
        expected_url = 'https://photo.url.s3.com'

        data = {'profile_photo': input_url}
        actual = ProfilePhotoHelper.create_profile_photo_url(data)

        mock_migrate_user_profile_photo_to_s3.assert_called_once_with(input_url)
        self.assertEqual(expected_url, actual)

    @patch(
        'amuse.services.usermanagement.profile_photo_helper.user_profile_photo_s3_url',
        return_value='https://photo.url.s3.com',
    )
    @patch(
        'amuse.services.usermanagement.profile_photo_helper.migrate_user_profile_photo_to_s3'
    )
    def test_create_profile_photo_url_if_profile_photo_does_not_start_with_http(
        self, mock_migrate_user_profile_photo_to_s3, mock_user_profile_photo_s3_url
    ):
        expected_url = 'https://photo.url.s3.com'
        photo_uuid = str(uuid4())
        data = {'profile_photo': photo_uuid}

        actual = ProfilePhotoHelper.create_profile_photo_url(data)
        self.assertEqual(expected_url, actual)

        self.assertEqual(mock_migrate_user_profile_photo_to_s3.call_count, 0)
        mock_user_profile_photo_s3_url.assert_called_once_with(photo_uuid)

    def test_create_profile_photo_url_from_uuid_if_profile_photo_does_not_exist(self):
        data = {}
        url = ProfilePhotoHelper.create_profile_photo_url_from_uuid(data)

        self.assertIsNone(url)

    @patch(
        'amuse.services.usermanagement.profile_photo_helper.user_profile_photo_s3_url',
        return_value='https://photo.url.com',
    )
    def test_create_profile_photo_url_from_uuid(self, mock_user_profile_photo_s3_url):
        photo_uuid = str(uuid4())
        data = {'profile_photo': photo_uuid}
        actual = ProfilePhotoHelper.create_profile_photo_url_from_uuid(data)

        self.assertEqual('https://photo.url.com', actual)
        mock_user_profile_photo_s3_url.assert_called_once_with(photo_uuid)
