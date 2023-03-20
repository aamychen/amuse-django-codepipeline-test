# -*- coding: utf-8 -*-
import logging
from django.template import Template, Context

from waffle import switch_is_active
from amuse.vendor.firebase import clients
from amuse.vendor.firebase.models import Payload, Notification
from amuse.models.utils import NotificationTemplate
from amuse.celery import app

logger = logging.getLogger(__name__)


class CloudMessagingService:
    def __init__(self):
        self.client = clients.CloudMessagingClient()

    def get_template(self, key):
        return NotificationTemplate.objects.filter(data__key=key).first()

    def render(self, str, context):
        t = Template(str)
        c = Context(context)
        return t.render(c)

    def construct_payload(self):
        return Payload(notification=Notification())

    def send(self, user, template_key, context=None):
        logger.info("Sending template '%s' to User.%d" % (template_key, user.id))

        if user.firebase_token:
            payload = self.construct_payload()
            notification = payload.notification
            payload.to = user.firebase_token
            template = self.get_template(template_key)

            if template:
                notification.title = self.render(template.data['title'], context)
                notification.body = self.render(template.data['body'], context)

                if 'data' in template.data:
                    data = {}
                    for key, val in template.data['data'].items():
                        data[key] = self.render(val, context)

                    payload.data = data

                return self.client.send(payload)
            else:
                logger.warning("Template for '%s' is missing" % (template_key))
        else:
            logger.warning("User.%d has no firebase_token" % (user.id))

    def send_release_notification(self, release):
        template_prefix = 'firebase:cm:release:'
        template_key = template_prefix + str(release.status)
        template_context = {'user': release.user, 'release': release}

        return self.send(release.user, template_key, template_context)


@app.task(bind=True, max_retries=3)
def release_notification_task(self, release_id):
    if switch_is_active('service:firebase:cm:enabled'):
        from releases.models import Release

        release = Release.objects.get(pk=release_id)
        cms = CloudMessagingService()
        try:
            cms.send_release_notification(release)
        except Exception as exc:
            raise self.retry(exc=exc)
    else:
        logger.info("Firebase is DISABLED.")
