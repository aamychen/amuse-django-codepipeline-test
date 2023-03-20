from django_hosts import patterns, host
from django.contrib import admin

host_patterns = patterns(
    '',
    host(r'api(-.*)?', 'amuse.urls.api', name='api'),
    host(r'app(-.*)?', 'amuse.urls.app', name='app'),
    host(r'admin(-.*)?', 'amuse.urls.admin', name='admin'),
)
