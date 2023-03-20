from __future__ import absolute_import

from celery import Celery
from django.conf import settings


app = Celery(
    'amuse',
    broker=settings.BROKER_URL,
    include=['amuse.tasks', 'amuse.cronjobs.tasks', 'amuse.vendor.segment.tasks'],
)

app.config_from_object('django.conf:settings')

if __name__ == '__main__':
    app.start()
