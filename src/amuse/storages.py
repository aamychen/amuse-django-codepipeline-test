from boto.s3.bucket import Bucket
from boto.s3.connection import S3Connection
from storages.backends.s3boto3 import S3Boto3Storage
from storages.utils import setting
from django.core.exceptions import ImproperlyConfigured


class S3Storage(S3Boto3Storage):
    def __init__(self, **settings):
        super().__init__(**settings)

    def get_default_settings(self):
        cloudfront_key_id = setting('AWS_CLOUDFRONT_KEY_ID')
        cloudfront_key = setting('AWS_CLOUDFRONT_KEY')
        if bool(cloudfront_key_id) ^ bool(cloudfront_key):
            raise ImproperlyConfigured(
                'Both AWS_CLOUDFRONT_KEY_ID and AWS_CLOUDFRONT_KEY must be '
                'provided together.'
            )

        if cloudfront_key_id:
            cloudfront_signer = self.get_cloudfront_signer(
                cloudfront_key_id, cloudfront_key
            )
        else:
            cloudfront_signer = None

        s3_access_key_id = setting('AWS_S3_ACCESS_KEY_ID')
        s3_secret_access_key = setting('AWS_S3_SECRET_ACCESS_KEY')
        s3_session_profile = setting('AWS_S3_SESSION_PROFILE')
        if (s3_access_key_id or s3_secret_access_key) and s3_session_profile:
            raise ImproperlyConfigured(
                'AWS_S3_SESSION_PROFILE should not be provided with '
                'AWS_S3_ACCESS_KEY_ID and AWS_S3_SECRET_ACCESS_KEY'
            )

        return {
            'access_key': setting('AWS_S3_ACCESS_KEY_ID', setting('AWS_ACCESS_KEY_ID')),
            'secret_key': setting(
                'AWS_S3_SECRET_ACCESS_KEY', setting('AWS_SECRET_ACCESS_KEY')
            ),
            'session_profile': setting('AWS_S3_SESSION_PROFILE'),
            'file_overwrite': setting('AWS_S3_FILE_OVERWRITE', True),
            'object_parameters': setting('AWS_S3_OBJECT_PARAMETERS', {}),
            'bucket_name': setting('AWS_STORAGE_BUCKET_NAME'),
            'querystring_auth': setting('AWS_QUERYSTRING_AUTH', True),
            'querystring_expire': setting('AWS_QUERYSTRING_EXPIRE', 3600),
            'signature_version': setting('AWS_S3_SIGNATURE_VERSION'),
            'location': setting('AWS_LOCATION', ''),
            'custom_domain': setting('AWS_S3_CUSTOM_DOMAIN'),
            'cloudfront_signer': cloudfront_signer,
            'addressing_style': setting('AWS_S3_ADDRESSING_STYLE'),
            'secure_urls': setting('AWS_S3_SECURE_URLS', True),
            'file_name_charset': setting('AWS_S3_FILE_NAME_CHARSET', 'utf-8'),
            'gzip': setting('AWS_IS_GZIPPED', False),
            'gzip_content_types': setting(
                'GZIP_CONTENT_TYPES',
                (
                    'text/css',
                    'text/javascript',
                    'application/javascript',
                    'application/x-javascript',
                    'image/svg+xml',
                ),
            ),
            'url_protocol': setting('AWS_S3_URL_PROTOCOL', 'http:'),
            'endpoint_url': setting('AWS_S3_ENDPOINT_URL'),
            'proxies': setting('AWS_S3_PROXIES'),
            'region_name': setting('AWS_S3_REGION_NAME'),
            'use_ssl': setting('AWS_S3_USE_SSL', True),
            'verify': setting('AWS_S3_VERIFY', None),
            'max_memory_size': setting('AWS_S3_MAX_MEMORY_SIZE', 0),
            'default_acl': setting('AWS_DEFAULT_ACL', None),
        }


class MinioBucket(Bucket):
    def set_acl(self, *args, **kwargs):
        pass


class MinioConnection(S3Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bucket_class = MinioBucket
