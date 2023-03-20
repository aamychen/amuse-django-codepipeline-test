import json
import logging
import re

from django.utils.timezone import now

logger = logging.getLogger(__name__)


class ViewLogBase:
    FILTERED_PLACEHOLDER = '[Filtered]'
    FILTERED_FIELDS = re.compile(
        'api|token|secret|password|signature|authorization', re.I
    )
    WHITELISTED_FIELDS = {'purchase_token'}

    def format_datetime(self, datetime):
        try:
            return datetime.strftime("%H:%M:%S.%f")
        except:
            return ''

    def collect_headers(self, environ):
        def parse_header_name(header):
            HTTP_PREFIX = "HTTP_"
            UNPREFIXED = {"CONTENT_TYPE", "CONTENT_LENGTH"}
            if header.startswith(HTTP_PREFIX):
                header = header[len(HTTP_PREFIX) :]
            elif header not in UNPREFIXED:
                return None
            return header.replace("_", "-").title()

        headers = {}
        for header, value in environ.items():
            name = parse_header_name(header)
            if name:
                headers[name] = value
        return headers

    def clean_data(self, data):
        if not data:
            return data
        if isinstance(data, list):
            return [self.clean_data(d) for d in data]
        if isinstance(data, dict):
            data = dict(data)
            for key, value in data.items():
                if isinstance(value, list) or isinstance(value, dict):
                    data[key] = self.clean_data(value)

                if key in self.WHITELISTED_FIELDS:
                    continue

                if self.FILTERED_FIELDS.search(key):
                    data[key] = self.FILTERED_PLACEHOLDER
        return data
