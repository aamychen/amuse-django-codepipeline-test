"""
Shared configuration options.

Contains settings that
* are shared between all environments.
* are secret and/or configurable.
"""
import base64
import os
import urllib
from datetime import timedelta

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from corsheaders.defaults import default_headers
from bananas.environment import env
from import_export.tmp_storages import CacheStorage

from amuse.settings.constants import *

SENTRY_DSN = env.get("SENTRY_DSN")
SENTRY_ENV = env.get("SENTRY_ENV")

if SENTRY_DSN and SENTRY_ENV:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENV,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.05,
    )

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.9/howto/deployment/checklist/
SECRET_KEY = env.get('DJANGO_SECRET_KEY')

DEBUG = env.get_bool('DJANGO_DEBUG', False)

# Only specify and do conditional checks with 'dev' or 'staging'.
# This returning `None` implies that the active environment is production.
AMUSE_ENV = env.get('AMUSE_ENV')

# Uploads
MEDIA_URL = env.get('MEDIA_URL', '/media/')
MEDIA_ROOT = env.get('MEDIA_ROOT', '/srv/amuse-uploads/')

# Assets CDN
ASSETS_CDN_DOMAIN = env.get('ASSETS_CDN_DOMAIN', None)

# AWS Settings
AWS_S3_ENDPOINT_URL = env.get('AWS_S3_ENDPOINT_URL', None)
AWS_S3_HOST = env.get('AWS_S3_HOST', 's3.amazonaws.com')
AWS_S3_PORT = env.get_int('AWS_S3_PORT', 443)
AWS_S3_REGION_NAME = env.get('AWS_S3_REGION_NAME', None)
AWS_S3_USE_SSL = env.get_bool('AWS_S3_USE_SSL', True)
AWS_S3_CALLING_FORMAT = env.get(
    'AWS_S3_CALLING_FORMAT', 'boto.s3.connection.SubdomainCallingFormat'
)

AWS_ACCESS_KEY_ID = env.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env.get('AWS_SECRET_ACCESS_KEY')
AWS_SQS_PREFIX = env.get('AWS_SQS_PREFIX')
AWS_QUERYSTRING_AUTH = env.get('AWS_QUERYSTRING_AUTH', True)
AWS_AUTO_CREATE_BUCKET = env.get_bool('AWS_AUTO_CREATE_BUCKET', False)

AWS_IAM_ROLE_ARN_REDSHIFT_S3 = env.get('AWS_IAM_ROLE_ARN_REDSHIFT_S3')

AWS_STORAGE_BUCKET_NAME = env.get('AWS_STORAGE_BUCKET_NAME')
AWS_COVER_ART_UPLOADED_BUCKET_NAME = env.get('AWS_COVER_ART_UPLOADED_BUCKET_NAME')
AWS_SONG_FILE_UPLOADED_BUCKET_NAME = env.get('AWS_SONG_FILE_UPLOADED_BUCKET_NAME')
AWS_SONG_FILE_TRANSCODED_BUCKET_NAME = env.get('AWS_SONG_FILE_TRANSCODED_BUCKET_NAME')
AWS_TRANSACTION_FILE_BUCKET_NAME = env.get('AWS_TRANSACTION_FILE_BUCKET_NAME')
AWS_PROFILE_PHOTO_BUCKET_NAME = env.get('AWS_PROFILE_PHOTO_BUCKET_NAME')
AWS_BULK_DELIVERY_JOB_BUCKET_NAME = env.get('AWS_BULK_DELIVERY_JOB_BUCKET_NAME')
AWS_SONG_FILE_TRANSCODER_PIPELINE = env.get('AWS_SONG_FILE_TRANSCODER_PIPELINE_ID')
AWS_SONG_FILE_STANDARD_PRIORITY_PIPELINE_ID = env.get(
    'AWS_SONG_FILE_STANDARD_PRIORITY_PIPELINE_ID'
)
AWS_BATCH_DELIVERY_BUCKET_NAME = env.get('AWS_BATCH_DELIVERY_BUCKET_NAME')
AWS_BATCH_DELIVERY_FILE_BUCKET_NAME = env.get('AWS_BATCH_DELIVERY_FILE_BUCKET_NAME')

AWS_SNS_USER = env.get('AWS_SNS_USER')
AWS_SNS_PASSWORD = env.get('AWS_SNS_PASSWORD')
AWS_SNS_SMART_LINK_TOPIC_ARN = env.get('AWS_SNS_SMART_LINK_TOPIC_ARN')

AMUSE_S3_CONNECTION = env.get('AMUSE_S3_CONNECTION')

# Audio Transcoder Service Settings
AUDIO_TRANSCODER_SERVICE_REQUEST_QUEUE_NAME = env.get(
    'AUDIO_TRANSCODER_SERVICE_REQUEST_QUEUE'
)
AUDIO_TRANSCODER_SERVICE_RESPONSE_TOPIC = env.get(
    'AUDIO_TRANSCODER_SERVICE_RESPONSE_TOPIC'
)

# Celery message broker settings
BROKER_URL = env.get('CELERY_BROKER_URL')
if BROKER_URL is None:
    BROKER_URL = 'sqs://%s:%s@' % (
        urllib.parse.quote(AWS_ACCESS_KEY_ID or '', safe=''),
        urllib.parse.quote(AWS_SECRET_ACCESS_KEY or '', safe=''),
    )

BROKER_TRANSPORT_OPTIONS = {'region': AWS_REGION, 'queue_name_prefix': AWS_SQS_PREFIX}

CELERY_ENABLE_REMOTE_CONTROL = False
CELERY_SEND_EVENTS = False
CELERY_ALWAYS_EAGER = env.get_bool('CELERY_ALWAYS_EAGER', False)
CELERY_TASK_RESULT_EXPIRES = env.get_int('CELERY_TASK_RESULT_EXPIRES', 3600)
CELERY_TASK_SERIALIZER = "pickle"
CELERY_ACCEPT_CONTENT = ['pickle', 'json']
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'

# Firebase API Keys
FIREBASE_API_SENDER_ID = env.get('FIREBASE_API_SENDER_ID')
FIREBASE_API_SERVER_KEY = env.get('FIREBASE_API_SERVER_KEY')

# Google API Keys
GOOGLE_SERVER_API_KEY = env.get('GOOGLE_SERVER_API_KEY')

# Google OAuth settings
GOOGLE_OAUTH2_CLIENT_ID = env.get('GOOGLE_OAUTH2_CLIENT_ID')
GOOGLE_OAUTH2_CLIENT_SECRET = env.get('GOOGLE_OAUTH2_CLIENT_SECRET')
GOOGLE_OAUTH2_REDIRECT_URI = env.get('GOOGLE_OAUTH2_REDIRECT_URI')

# Zendesk settings
ZENDESK_API_USER = env.get('ZENDESK_API_USER', '')
ZENDESK_API_TOKEN = env.get('ZENDESK_API_TOKEN', '')

# Mandrill & Email settings
MANDRILL_API_KEY = env.get('MANDRILL_API_KEY')

EMAIL_BACKEND = env.get('DJANGO_EMAIL_BACKEND')

# Segment settings
SEGMENT_WRITE_KEY = env.get('SEGMENT_WRITE_KEY')
SEGMENT_UPDATE_IS_PRO_STATE = env.get_bool('SEGMENT_UPDATE_IS_PRO_STATE', False)
SEGMENT_API_TOKEN = env.get('SEGMENT_API_TOKEN')

# CustomerIO
CUSTOMERIO_SITE_ID = env.get('CUSTOMERIO_SITE_ID')
CUSTOMERIO_API_KEY = env.get('CUSTOMERIO_API_KEY')

# Rebrandly
REBRANDLY_API_KEY = env.get('REBRANDLY_API_KEY')
REBRANDLY_DOMAIN = env.get('REBRANDLY_DOMAIN')
REBRANDLY_ENABLED = env.get_bool('REBRANDLY_ENABLED', False)
REBRANDLY_APP_IDS = env.get('REBRANDLY_APP_IDS', '')

# Hyperwallet settings
HYPERWALLET_USER = env.get('HYPERWALLET_USER')
HYPERWALLET_PASSWORD = env.get('HYPERWALLET_PASSWORD')
HYPERWALLET_PROGRAM_TOKEN_SE = env.get('HYPERWALLET_PROGRAM_TOKEN_SE')
HYPERWALLET_PROGRAM_TOKEN_REST_OF_WORLD = env.get(
    'HYPERWALLET_PROGRAM_TOKEN_REST_OF_WORLD'
)
HYPERWALLET_PROGRAM_TOKEN_EU = env.get('HYPERWALLET_PROGRAM_TOKEN_EU')
HYPERWALLET_ENDPOINT = env.get('HYPERWALLET_ENDPOINT')

# Revenue System
REVENUE_API_URL = env.get('REVENUE_API_URL', 'http://localhost')

# Slayer
SLAYER_GRPC_HOST = env.get('SLAYER_GRPC_HOST', '127.0.0.1')
SLAYER_GRPC_PORT = env.get('SLAYER_GRPC_PORT', 9090)
SLAYER_GRPC_SSL = env.get('SLAYER_GRPC_SSL', 'noverify')

# --------------------------------------------------
# Spotify API
# --------------------------------------------------

# Credentials for Analytics API
SPOTIFY_CLIENT_ID = env.get('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = env.get('SPOTIFY_CLIENT_SECRET')

# Credentials for Web API
SPOTIFY_API_CLIENT_ID = env.get('SPOTIFY_API_CLIENT_ID')
SPOTIFY_API_CLIENT_SECRET = env.get('SPOTIFY_API_CLIENT_SECRET')

# Credentials for Atlas API
SPOTIFY_ATLAS_AMUSE_CLIENT_ID = env.get('SPOTIFY_ATLAS_AMUSE_CLIENT_ID', None)
SPOTIFY_ATLAS_CODE_VERIFIER = env.get('SPOTIFY_ATLAS_CODE_VERIFIER', None)
SPOTIFY_ATLAS_CODE_CHALLENGE = env.get('SPOTIFY_ATLAS_CODE_CHALLENGE', None)
SPOTIFY_ATLAS_STATE = env.get('SPOTIFY_ATLAS_STATE', None)
SPOTIFY_ATLAS_COOKIE = env.get('SPOTIFY_ATLAS_COOKIE', None)

# Credentials for Spotify for Artists integration
S4A_API_CLIENT_ID = env.get('S4A_API_CLIENT_ID')
S4A_API_CLIENT_SECRET = env.get('S4A_API_CLIENT_SECRET')
S4A_INVITE_CLIENT_SECRET = env.get('S4A_INVITE_CLIENT_SECRET')

# --------------------------------------------------
# AudioMack API
# --------------------------------------------------

AUDIOMACK_CONSUMER_KEY = env.get('AUDIOMACK_CONSUMER_KEY')
AUDIOMACK_CONSUMER_SECRET = env.get('AUDIOMACK_CONSUMER_SECRET')
AUDIOMACK_CALLBACK_API = env.get('AUDIOMACK_CALLBACK_API')

# --------------------------------------------------
# ACRCloud settings
# --------------------------------------------------

ACRCLOUD_ACCESS_KEY = env.get('ACRCLOUD_ACCESS_KEY')
ACRCLOUD_ACCESS_SECRET = env.get('ACRCLOUD_ACCESS_SECRET')
ACRCLOUD_ENDPOINT = env.get('ACRCLOUD_ENDPOINT')

# Logger settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'messageOnly': {'format': '%(message)s', 'datefmt': '%Y-%m-%d %H:%M:%S %z'},
        '-v': {
            'format': '[%(asctime)s] %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S %z',
        },
        '-vv': {
            'format': '[%(asctime)s] %(levelname)s - %(name)s.%(funcName)s(): '
            '%(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S %z',
        },
        '-vvv': {
            'format': '[%(asctime)s] %(levelname)s - %(name)s.%(funcName)s() '
            '(%(process)d / %(thread)d): %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S %z',
        },
    },
    'handlers': {
        'logstash': {'class': 'amuse.logging.AmuseStreamHandler', 'level': 'DEBUG'},
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'messageOnly',
            'level': 'DEBUG',
        },
        'slack': {'class': 'amuse.logging.SlackHandler', 'level': 'ERROR'},
    },
    'loggers': {
        # Our apps
        'amuse': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'app': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'audiblemagic': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'codes': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'contenttollgate': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'countries': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'mailchimp': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'payments': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'releases': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'segment': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'subscriptions': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'transcoder': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'users': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'website': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        # Logging the API calls in Logstash format separately
        'api': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['logstash', 'slack'],
        },
        # Logging apple subscription related logs togther.
        'apple.subscription': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['logstash', 'slack'],
        },
        # Logging in tasks through the celery logger puts messages in this namespace
        'celery': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
        'pyslayer': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'handlers': ['console', 'slack'],
        },
    },
    'root': {'level': 'WARNING', 'handlers': ['console', 'slack']},  # catch all modules
}

DATABASES = {
    'default': {
        'ENGINE': env.get('DJANGO_DB_DEFAULT_ENGINE', 'django.db.backends.postgresql'),
        'NAME': 'amuse',
        'USER': env.get('DJANGO_DB_DEFAULT_USER', 'postgres'),
        'PASSWORD': env.get('DJANGO_DB_DEFAULT_PASSWORD', 'postgres'),
        'HOST': env.get('DJANGO_DB_DEFAULT_HOST'),
        'PORT': env.get('DJANGO_DB_DEFAULT_PORT', 5432),
    },
    'replica': {
        'ENGINE': env.get('DJANGO_DB_REPLICA_ENGINE', 'django.db.backends.postgresql'),
        'NAME': 'amuse',
        'USER': env.get('DJANGO_DB_REPLICA_USER', 'postgres'),
        'PASSWORD': env.get('DJANGO_DB_REPLICA_PASSWORD', 'postgres'),
        'HOST': env.get('DJANGO_DB_REPLICA_HOST'),
        'PORT': env.get('DJANGO_DB_REPLICA_PORT', 5432),
    },
}

CACHES = {
    'default': {'BACKEND': 'amuse.cache.AmuseDatabaseCache', 'LOCATION': 'django_cache'}
}

if env.get('REDIS_CACHE_HOSTS'):
    cache_hosts = env.get_list('REDIS_CACHE_HOSTS')

    if len(cache_hosts) == 1:
        cache_hosts = cache_hosts[0]

    CACHES['default'] = {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": cache_hosts,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }

# Application specific settings
API_URL = env.get('AMUSE_API_URL')
WWW_URL = env.get('AMUSE_WWW_URL')
APP_URL = env.get('AMUSE_APP_URL')
ADMIN_URL = env.get('AMUSE_ADMIN_URL')
WRB_URL = env.get('AMUSE_WRB_URL')
LINKS_BACKEND_URL = env.get('LINKS_BACKEND_URL')

# FUGA settings
FUGA_FTP_HOSTNAME = env.get('FUGA_FTP_HOSTNAME')
FUGA_FTP_USERNAME = env.get('FUGA_FTP_USERNAME')
FUGA_FTP_PASSWORD = env.get('FUGA_FTP_PASSWORD')

# Apple settings
APPLE_DELIVERY_SERVICE_URL = env.get('APPLE_DELIVERY_SERVICE_URL')
APPLE_DELIVERY_SERVICE_REQUEST_QUEUE = env.get('APPLE_DELIVERY_SERVICE_REQUEST_QUEUE')
APPLE_DELIVERY_SERVICE_RESPONSE_TOPIC = env.get('APPLE_DELIVERY_SERVICE_RESPONSE_TOPIC')

# Slack webhook for notifications
SLACK_WEBHOOK_URL_NOTIFICATIONS = env.get('SLACK_WEBHOOK_URL_NOTIFICATIONS')
SLACK_WEBHOOK_URL_ERRORS = env.get('SLACK_WEBHOOK_URL_ERRORS')

# Geo IP database location
GEOIP_PATH = env.get('GEOIP_PATH', '/home/ubuntu/')

# Block these IPs from specific endpoints and actions
IP_BLOCK_THROTTLE = {}

# Pass a ';'-separated string with IPs to not throttle
IP_WHITE_LIST_THROTTLE = env.get('IP_WHITE_LIST_THROTTLE') or []
if IP_WHITE_LIST_THROTTLE:
    IP_WHITE_LIST_THROTTLE = IP_WHITE_LIST_THROTTLE.strip(';').split(';')

CORS_ALLOW_HEADERS = default_headers + ('x-user-agent', 'x-trigger-event')

# Twilio
TWILIO_SID = env.get('TWILIO_SID')
TWILIO_TOKEN = env.get('TWILIO_TOKEN')
TWILIO_FROM = env.get('TWILIO_FROM')

MINFRAUD_LICENCE_KEY = env.get('MINFRAUD_LICENCE_KEY')

JWT_SECRET = env.get('JWT_SECRET')
JWT_SIGN_VERIFY_KMS_ARN = env.get('JWT_SIGN_VERIFY_KMS_ARN')
JWT_KMS_PUBKEY_CACHE_TTL_SECS = env.get('JWT_KMS_PUBKEY_CACHE_TTL_SECS', 5)

# Adyen payments
ADYEN_PLATFORM = env.get('ADYEN_PLATFORM')
ADYEN_MERCHANT_ACCOUNT = env.get('ADYEN_MERCHANT_ACCOUNT')
ADYEN_API_KEY = env.get('ADYEN_API_KEY')
ADYEN_ORIGIN_KEY = env.get('ADYEN_ORIGIN_KEY')
ADYEN_NOTIFICATION_USER = env.get('ADYEN_NOTIFICATION_USER')
ADYEN_NOTIFICATION_PASSWORD = env.get('ADYEN_NOTIFICATION_PASSWORD')
ADYEN_NOTIFICATION_HMAC = env.get('ADYEN_NOTIFICATION_HMAC')
ADYEN_LIVE_ENDPOINT_PREFIX = env.get('ADYEN_LIVE_ENDPOINT_PREFIX')

# Apple Payments
APPLE_KEY = env.get('APPLE_KEY')
APPLE_PLATFORM = env.get('APPLE_PLATFORM')
APPLE_VALIDATION_URL = env.get('APPLE_VALIDATION_URL')

# Apple Social Login
SOCIAL_AUTH_APPLE_KEY_ID = env.get('SOCIAL_AUTH_APPLE_KEY_ID')
SOCIAL_AUTH_APPLE_TEAM_ID = env.get('SOCIAL_AUTH_APPLE_TEAM_ID')
SOCIAL_AUTH_APPLE_PRIVATE_KEY = env.get('SOCIAL_AUTH_APPLE_PRIVATE_KEY')
SOCIAL_AUTH_APPLE_CLIENT_ID = env.get('SOCIAL_AUTH_APPLE_CLIENT_ID', 'io.amuse.ios')
SOCIAL_AUTH_APPLE_WEB_CLIENT_ID = env.get(
    'SOCIAL_AUTH_APPLE_WEB_CLIENT_ID', 'io.amuse.artist'
)

IMPORT_EXPORT_TMP_STORAGE_CLASS = CacheStorage

FFWD_RECOUP_SNS_TOPIC = env.get('FFWD_RECOUP_SNS_TOPIC')
FFWD_NOTIFICATION_SNS_TOPIC = env.get('FFWD_NOTIFICATION_SNS_TOPIC')
SMART_LINK_CALLBACK_SNS_TOPIC = env.get('SMART_LINK_CALLBACK_SNS_TOPIC')

APPSFLYER_ENABLED = env.get_bool('APPSFLYER_ENABLED')
APPSFLYER_IOS_APP_ID = env.get('APPSFLYER_IOS_APP_ID')
APPSFLYER_ANDROID_APP_ID = env.get('APPSFLYER_ANDROID_APP_ID')
APPSFLYER_DEV_KEY = env.get('APPSFLYER_DEV_KEY')
APPSFLYER_WEB_DEV_KEY = env.get('APPSFLYER_WEB_DEV_KEY')
APPSFLYER_BRAND_BUNDLE_ID = env.get('APPSFLYER_BRAND_BUNDLE_ID')

GOOGLE_PLAY_API_SERVICE_ACCOUNT = env.get('GOOGLE_PLAY_API_SERVICE_ACCOUNT')
ANDROID_APP_PACKAGE = env.get('ANDROID_APP_PACKAGE')
ANDROID_APP_MFA_HASH = env.get('ANDROID_APP_MFA_HASH')
REPORT_DUPLICATE_GOOGLE_SUBSCRIPTIONS_TO = env.get(
    'REPORT_DUPLICATE_GOOGLE_SUBSCRIPTIONS_TO'
)

IMPACT_ENABLED = env.get_bool('IMPACT_ENABLED')
IMPACT_SID = env.get('IMPACT_SID')
IMPACT_PASSWORD = env.get('IMPACT_PASSWORD')

# Release delivery service
RELEASE_DELIVERY_SERVICE_REQUEST_QUEUE = env.get(
    'RELEASE_DELIVERY_SERVICE_REQUEST_QUEUE'
)
RELEASE_DELIVERY_SERVICE_RESPONSE_TOPIC = env.get(
    'RELEASE_DELIVERY_SERVICE_RESPONSE_TOPIC'
)

SMART_LINK_MESSAGE_BATCH_SIZE = env.get_int('SMART_LINK_MESSAGE_BATCH_SIZE', 200)

FUGA_API_USER = env.get('FUGA_API_USER')
FUGA_API_PASSWORD = env.get('FUGA_API_PASSWORD')
FUGA_API_URL = env.get('FUGA_API_URL')
FUGA_API_CACHE_COOKIE_KEY = env.get('FUGA_API_CACHE_COOKIE_KEY', "fuga_api_cookie_key")
FUGA_PARSER_NUM_RELEASES = env.get_int('FUGA_PARSER_NUM_RELEASES', 10)
FUGA_PARSER_NUM_RELEASES_FOR_DSP_HISTORY = env.get_int(
    'FUGA_PARSER_NUM_RELEASES_FOR_DSP_HISTORY', 10
)
FUGA_API_DELAY_IN_MS = env.get_int('FUGA_API_DELAY_IN_MS', 100)

SINCH_BATCH_API_ENDPOINT = env.get("SINCH_BATCH_API_ENDPOINT")
SINCH_US_SERVICE_PLAN_ID = env.get("SINCH_US_SERVICE_PLAN_ID")
SINCH_US_API_TOKEN = env.get("SINCH_US_API_TOKEN")
SINCH_US_SENDER = env.get("SINCH_US_SENDER")
SINCH_CA_SERVICE_PLAN_ID = env.get("SINCH_CA_SERVICE_PLAN_ID")
SINCH_CA_API_TOKEN = env.get("SINCH_CA_API_TOKEN")
SINCH_CA_SENDER = env.get("SINCH_CA_SENDER")
SINCH_WW_SERVICE_PLAN_ID = env.get("SINCH_WW_SERVICE_PLAN_ID")
SINCH_WW_API_TOKEN = env.get("SINCH_WW_API_TOKEN")
SINCH_WW_SENDER = env.get("SINCH_WW_SENDER")

HW_EMBEDDED_USER = env.get("HW_EMBEDDED_USER")
HW_EMBEDDED_PASSWORD = env.get("HW_EMBEDDED_PASSWORD")
HW_EMBEDDED_SERVER = env.get("HW_EMBEDDED_SERVER")
HW_EMBEDDED_PROGRAM_TOKEN_SE = env.get("HW_EMBEDDED_PROGRAM_TOKEN_SE")
HW_EMBEDDED_PROGRAM_TOKEN_REST_OF_WORLD = env.get(
    "HW_EMBEDDED_PROGRAM_TOKEN_REST_OF_WORLD"
)
HW_EMBEDDED_PROGRAM_TOKEN_EU = env.get("HW_EMBEDDED_PROGRAM_TOKEN_EU")
HYPERWALLET_NOTIFICATION_USER = env.get('HYPERWALLET_NOTIFICATION_USER')
HYPERWALLET_NOTIFICATION_PASSWORD = env.get('HYPERWALLET_NOTIFICATION_PASSWORD')

GCP_SERVICE_ACCOUNT_JSON = env.get('GCP_SERVICE_ACCOUNT_JSON')
PUBSUB_TRANSACTION_STATEMENT_TOPIC = env.get('PUBSUB_TRANSACTION_STATEMENT_TOPIC')
PUBSUB_RELEASE_VALIDATION_TOPIC = env.get('PUBSUB_RELEASE_VALIDATION_TOPIC')
RELEASE_ANALYSIS_CLIENT_ID = env.get('RELEASE_ANALYSIS_CLIENT_ID')

CURRENCYLAYER_ACCESS_KEY = env.get('CURRENCYLAYER_ACCESS_KEY')
BULK_EDIT_MAX_USERS = env.get_int('BULK_EDIT_MAX_USERS', 500)

GOOGLE_CAPTCHA_ENABLED = env.get_bool('GOOGLE_CAPTCHA_ENABLED', True)
GOOGLE_CAPTCHA_SECRET_KEY = env.get(
    'GOOGLE_CAPTCHA_SECRET_KEY', '6LfNB5wjAAAAABnb_t-xiQ8KCgf4xoetEGPLdegy'
)
GOOGLE_CAPTCHA_ENDPOINT = env.get(
    'GOOGLE_CAPTCHA_ENDPOINT', 'https://www.google.com/recaptcha/api/siteverify'
)
GOOGLE_CAPTCHA_SCORE_THRESHOLD = env.get('GOOGLE_CAPTCHA_SCORE_THRESHOLD', 0.3)

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=365),
    'ALGORITHM': 'RS256',
    'SIGNING_KEY': env.get('JWT_AUTH_PRIVATE_KEY', ''),
    'VERIFYING_KEY': env.get('JWT_AUTH_PUBLIC_KEY', ''),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
}

CLOUDFLARE_CERTS = env.get("CLOUDFLARE_CERTS")
CLOUDFLARE_AUD = env.get("CLOUDFLARE_AUD")

OTP_JWT_SECRET = env.get('OTP_JWT_SECRET')
OTP_JWT_EXP_MINUTES = env.get('OTP_JWT_EXP_MINUTES')

AUTH_SIGNING_KEY = base64.b64decode(env.get('JWT_AUTH_PRIVATE_KEY', ''))
AUTH_VERIFY_KEY = base64.b64decode(env.get('JWT_AUTH_PUBLIC_KEY', ''))
AUTH_TOKEN_GENERATOR_CLASS = env.get('AUTH_TOKEN_GENERATOR_CLASS')
ACCESS_TOKEN_EXP_MINUTES = env.get("ACCESS_TOKEN_EXP_MINUTES", 180)
REFRESH_TOKEN_EXP_DAYS = env.get("REFRESH_TOKEN_EXP_DAYS", 2)

# set cookie secure = False  for local testing
UNSECURE_COOKIE = env.get('UNSECURE_COOKIE', False)
