"""
Shared configuration options.

Contains settings that
* are shared between all environments.
* are NOT secret.
* are NOT configurable.
"""
import os
from decimal import Decimal

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


# Path config.
AUDIBLE_MAGIC_DIR = '%s/audiblemagic' % BASE_DIR
AUDIBLE_MAGIC_CONF = '%s/config.xml' % AUDIBLE_MAGIC_DIR


ALLOWED_HOSTS = ['*']
CORS_ORIGIN_ALLOW_ALL = True
ROOT_URLCONF = 'amuse.urls.app'
ROOT_HOSTCONF = 'amuse.hosts'
DEFAULT_HOST = 'app'
WSGI_APPLICATION = 'amuse.wsgi.application'
DEFAULT_FROM_EMAIL = 'noreply@amuse.io'
DATA_UPLOAD_MAX_NUMBER_FIELDS = 4000
TEST_RUNNER = 'amuse.tests.runner.PytestTestRunner'


STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Release ID for new `vendor_id` format
APPLE_XML_VENDOR_ID_CUTOFF = 198168

WHITENOISE_MAX_AGE = 1000000

# Application definition
INSTALLED_APPS = [
    'whitenoise.runserver_nostatic',
    'contenttollgate.apps.ContentTollgateConfig',
    'corsheaders',
    'django_non_dark_admin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    'bitfield',
    'django_hosts',
    'import_export',
    'nested_inline',
    'storages',
    'waffle',
    'simple_history',
    'codes.apps.CodesConfig',
    'countries.apps.CountriesConfig',
    'releases.apps.ReleasesConfig',
    'transcoder.apps.TranscoderConfig',
    'users.apps.UsersConfig',
    'website.apps.WebsiteConfig',
    'app.apps.AppBaseConfig',
    'amuse.apps.AmuseConfig',
    'payments.apps.PaymentsConfig',
    'subscriptions.apps.SubscriptionsConfig',
    'artistmanager',
    'amuse.services.delivery',
    'payouts',
    'django_celery_beat',
    'django_celery_results',
    'slayer',
    'drf_spectacular',
    'apidocs',
]


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django_hosts.middleware.HostsRequestMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_hosts.middleware.HostsResponseMiddleware',
    'amuse.cloudflare.CloudflareAccessAuthenticationMiddleware',
    'waffle.middleware.WaffleMiddleware',
]


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates/')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ]
        },
    }
]


# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'
    },
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Auth user model to use
AUTH_USER_MODEL = 'users.User'


AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']


# REST framework global settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
}

# AWS Constants
AWS_REGION = 'eu-west-1'
AWS_FLAC_PRESET_ID = '1351620000001-300110'
AWS_MP3128K_PRESET_ID = '1351620000001-300040'


# External URLs
FIREBASE_API_URL = 'https://fcm.googleapis.com/fcm/send'
ZENDESK_API_URL = 'https://amusesupport.zendesk.com/'

# Lyrics analysis service

LYRICS_SERVICE_REQUEST_QUEUE = "lyrics-analysis-service-request"
LYRICS_SERVICE_RESPONSE_TOPIC = (
    "arn:aws:sns:eu-west-1:097538760983:lyrics-analysis-service-response"
)

# Audio recognition service

AUDIO_RECOGNITION_SERVICE_REQUEST_QUEUE = "audio-recognition-service-request"
AUDIO_RECOGNITION_SERVICE_RESPONSE_TOPIC = (
    "arn:aws:sns:eu-west-1:097538760983:audio-recognition-service-response"
)

MINFRAUD_ACCOUNT_ID = 141920

# TODO Remove UK if needed after Brexit
EU_COUNTRIES = (
    'AT',
    'BE',
    'BG',
    'CY',
    'CZ',
    'DE',
    'DK',
    'EE',
    'ES',
    'FI',
    'FR',
    'GB',
    'GR',
    'HR',
    'HU',
    'IE',
    'IT',
    'LT',
    'LU',
    'LV',
    'MT',
    'NL',
    'PL',
    'PT',
    'RO',
    'SI',
    'SK',
)

# In Direct integration GB is in ROW program
# This is just temp until we fully switch to Direct then EU_COUNTRIES will be only used.
EU_COUNTRIES_DIRECT = (
    'AT',
    'BE',
    'BG',
    'CY',
    'CZ',
    'DE',
    'DK',
    'EE',
    'ES',
    'FI',
    'FR',
    'GR',
    'HR',
    'HU',
    'IE',
    'IT',
    'LT',
    'LU',
    'LV',
    'MT',
    'NL',
    'PL',
    'PT',
    'RO',
    'SI',
    'SK',
    'NO',
    'IS',
    'LI',
    'VA',
    'GF',
    'MF',
    'RE',
    'FO',
    'GL',
    'PM',
    'MC',
    'BL',
    'YT',
    'SM',
)


HYPERWALLET_MIN_WITHDRAWAL_LIMIT = Decimal("10.00")

# $100K is Hyperwallet's upper limit for a single payment
HYPERWALLET_MAX_WITHDRAWAL_LIMIT = Decimal("10000.00")
HYPERWALLET_VERIFIED_USERS_MAX_WITHDRAWAL_LIMIT = Decimal("40000.00")
HYPERWALLET_MAX_ADVANCE_WITHDRAWAL_LIMIT = Decimal("60000.00")
# Cancel payment if any of this errors is encountered
HYPERWALLET_CANCEL_ERROR_CODES = [
    "CONSTRAINT_VIOLATIONS",
    "ACCOUNT_STATUS_FLAGGED",
    "LIMIT_SUBCEEDED",
    "AMOUNT_LESS_THAN_FEE",
    "INCORRECT_FUNDING_PROGRAM",
    "LIMIT_EXCEEDED",
    "INSUFFICIENT_FUNDS",
    "PERIODIC_LIMIT_EXCEEDED",
    "EXTERNAL_ACCOUNT_TYPE_NOT_SUPPORTED",
]

ARTIST_NAME_MATCH_RATIO = 90

APPLE_STAGING_WEBHOOK_URL = 'https://app-staging.amuse.io/subscriptions/apple/'

SPOTIFY_ARTIST_URL = 'https://open.spotify.com/artist/{}'

AUDIOMACK_ARTIST_URL = 'https://audiomack.com/{}'

ADYEN_3DS_WEBAPP_RETURN_PATH = '#/studio?paymentsuccess='

TARGET_ICC_PROFILE = 'releases/sRGB-IEC61966-2.1.icc'

NONLOCALIZED_PAYMENTS_COUNTRY = 'US'

GCP_PUBSUB_PUBLISH_TIMEOUT = 10

SPECTACULAR_SETTINGS = {
    'TITLE': 'Amuse Django',
    'DESCRIPTION': 'Amuse Django REST API',
    'VERSION': None,  # Use versioning via DRF
    'SCHEMA_PATH_PREFIX_TRIM': True,
    'SERVE_PUBLIC': False,
    'SERVE_AUTHENTICATION': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
    },
    "PREPROCESSING_HOOKS": ["apidocs.filters.preprocessing_filter_spec"],
    'SCHEMA_PATH_PREFIX': '/api/analytics/artist',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': False,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAdminUser'],
}

# Fixing Django3.2 warnings
# https://docs.djangoproject.com/en/3.2/releases/3.2/#customizing-type-of-auto-created-primary-keys
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
DISABLE_DARK_MODE = True
CAPTCHA_HEADER_KEY = 'HTTP_G-RECAPTCHA-RESPONSE'
CAPTCHA_BODY_KEY = 'g-recaptcha-response'

OTP_COOKIE_NAME = 'otp'
ACCESS_COOKIE_NAME = 'access'
REFRESH_COOKIE_NAME = 'refresh'
MIN_PASSWORD_LENGTH = 8
