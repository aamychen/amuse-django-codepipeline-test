import json
import logging
import os
from contextlib import contextmanager
from unittest import mock

import responses
from bananas.environment import env
from django.conf import settings
from django.utils.http import urlencode
from rest_framework import status
from rest_framework.test import APITestCase
from waffle.models import Switch


API_V2_ACCEPT_VALUE = 'application/json; version=2'
API_V3_ACCEPT_VALUE = 'application/json; version=3'
API_V4_ACCEPT_VALUE = 'application/json; version=4'
API_V5_ACCEPT_VALUE = 'application/json; version=5'
API_V6_ACCEPT_VALUE = 'application/json; version=6'
API_V7_ACCEPT_VALUE = 'application/json; version=7'


class AmuseAPITestCase(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.configure()

    @classmethod
    def configure(cls):
        """
        Configure django here to prevent wrong env/settings being used by tests
        """
        settings.AWS_REGION = 'placeholder'

        # Set tests specific log level and limit to console handler
        settings.LOGGING['disable_existing_loggers'] = True
        for logger in settings.LOGGING.get('loggers', {}).values():
            logger['level'] = env.get('DJANGO_LOG_LEVEL_TESTS', 'CRITICAL')
            logger['handlers'] = ['console']
        logging.config.dictConfig(settings.LOGGING)

    def _mock_response(
        self, status=status.HTTP_200_OK, content=None, raise_for_status=None
    ):
        response = mock.Mock()
        response.status_code = status
        response.content = json.dumps(content)
        response.json.return_value = content
        if raise_for_status is not None:
            response.raise_for_status.side_effect = raise_for_status
        return response

    def _as_query_string(self, params):
        return {'QUERY_STRING': urlencode(params, doseq=True)}

    @contextmanager
    def _file(self, filename=None):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        filename = filename or 'amuse.jpg'
        file_path = os.path.join(current_dir, 'data', filename)
        with open(file_path, 'rb+') as f:
            yield filename, f

    @contextmanager
    def _file_url(self, filename=None):
        with responses.RequestsMock() as rsps:
            with self._file(filename) as (filename, f):
                url = f'http://foo.bar/{filename}'
                rsps.add(responses.GET, url, body=f.read(), status=200)
                yield filename, f, url

    def _enable_switch(self, name):
        switch, created = Switch.objects.get_or_create(
            name=name, defaults=dict(active=True)
        )
        if not created:
            switch.active = True
            switch.save()
