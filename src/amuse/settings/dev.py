"""
Settings specific to local dev environment (docker)
"""
from .unified import *

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        '-vv': {
            'format': '[%(asctime)s] %(levelname)s - %(name)s.%(funcName)s(): '
            '%(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S %z',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': '-vv',
            'level': 'DEBUG',
        }
    },
    'loggers': {
        # Our apps
        'amuse': {'level': 'DEBUG', 'handlers': ['console']},
        'payments': {'level': 'DEBUG', 'handlers': ['console']},
        # Silence slack stuff in dev
        'amuse.slack': {'level': 'ERROR', 'handlers': ['console']},
        'analytics': {'level': 'DEBUG', 'handlers': ['console']},
        'app': {'level': 'DEBUG', 'handlers': ['console']},
        'audiblemagic': {'level': 'DEBUG', 'handlers': ['console']},
        'codes': {'level': 'DEBUG', 'handlers': ['console']},
        'contenttollgate': {'level': 'DEBUG', 'handlers': ['console']},
        'countries': {'level': 'DEBUG', 'handlers': ['console']},
        'mailchimp': {'level': 'DEBUG', 'handlers': ['console']},
        'releases': {'level': 'DEBUG', 'handlers': ['console']},
        'transcoder': {'level': 'DEBUG', 'handlers': ['console']},
        'users': {'level': 'DEBUG', 'handlers': ['console']},
        'website': {'level': 'DEBUG', 'handlers': ['console']},
        # Logging in tasks through the celery logger puts messages in this namespace
        'celery': {'level': 'DEBUG', 'handlers': ['console']},
        'pyslayer': {'level': 'DEBUG', 'handlers': ['console']},
    },
    'root': {'level': 'WARNING', 'handlers': ['console']},
}


INSTALLED_APPS += ['django_extensions']

REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] += (
    'rest_framework.renderers.BrowsableAPIRenderer',
)

# ============================================================================
DEBUG_TOOLBAR = False  # Set `true` in order to activate Django debug toolbar
# ----------------------------------------------------------------------------
if DEBUG_TOOLBAR:
    INSTALLED_APPS += ['debug_toolbar']

    DEBUG_TOOLBAR_CONFIG = {
        # This line was added to make sure that the django debug toolbar appears
        # when you run your app in docker.
        'SHOW_TOOLBAR_CALLBACK': lambda request: not request.is_ajax()
    }

    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
# ============================================================================

# Our office IP
IP_WHITE_LIST_THROTTLE += ['217.31.163.186']
