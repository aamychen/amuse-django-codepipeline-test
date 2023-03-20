import json
import logging
import requests
import socket

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from logstash import LogstashFormatterVersion1

from amuse.utils import parsed_django_request_string


logger = logging.getLogger('api')


class SlackHandler(logging.Handler):
    COLOR_ERR = '#d50200'
    COLOR_WARN = '#de9e31'
    COLOR_INFO = '#2830ff'
    COLOR_DEBUG = '#2fa44f'
    COLOR_NOTSET = '#FAE62D'

    LEVEL_COLORS = {
        logging.CRITICAL: COLOR_ERR,
        logging.ERROR: COLOR_ERR,
        logging.WARN: COLOR_WARN,
        logging.INFO: COLOR_INFO,
        logging.DEBUG: COLOR_DEBUG,
    }

    def emit(self, record):
        payload = {
            "attachments": [
                {
                    "color": self.level_color(record),
                    "fallback": record.getMessage(),
                    "text": "```%s```" % self.format(record),
                    "footer": "%s · %s" % (record.levelname, socket.gethostname()),
                    "mrkdwn_in": ["text"],
                }
            ]
        }
        if not settings.SLACK_WEBHOOK_URL_ERRORS:
            return
        requests.post(settings.SLACK_WEBHOOK_URL_ERRORS, json=payload)

    def level_color(self, record):
        if record.levelno in self.LEVEL_COLORS:
            return self.LEVEL_COLORS[record.levelno]
        return self.COLOR_NOTSET


class AmuseLogFormatter(LogstashFormatterVersion1):
    @classmethod
    def serialize(cls, message):
        message['@version'] = '1.1'
        if message['logger_name'] == 'django.request':
            message.update(**parsed_django_request_string(message['request']))
            del message['request']
        return json.dumps(message, cls=DjangoJSONEncoder)


class AmuseStreamHandler(logging.StreamHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.formatter = AmuseLogFormatter()
