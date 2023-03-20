import hashlib
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_notification(payload):
    if not settings.SLACK_WEBHOOK_URL_NOTIFICATIONS:
        logger.warning('Slack notifications are not configured.')
        return
    return requests.post(settings.SLACK_WEBHOOK_URL_NOTIFICATIONS, json=payload)


def post_release_completed(status, release):
    release_link = '{0}releases/release/{1}/change'.format(
        settings.ADMIN_URL, release.id
    )
    user_link = "https://admin.amuse.io/users/user/%d/change" % release.user.id
    attachment_text = "Release <%s|%s> by <%s|%s> was `%s`" % (
        release_link,
        release.name,
        user_link,
        str(release.user),
        status.upper(),
    )
    fallback_text = "Release %s by %s was %s" % (
        release.name,
        str(release.user),
        status.upper(),
    )
    payload = {
        "attachments": [
            {
                "color": hashlib.md5(str(release.id).encode('utf-8')).hexdigest()[:6],
                "text": attachment_text,
                "fallback": fallback_text,
                "mrkdwn_in": ["text"],
            }
        ]
    }
    return send_notification(payload)


def post_user_created(user):
    link = '{0}users/user/{1}/change'.format(settings.ADMIN_URL, user.id)
    footer = user.country or ''
    if user.phone:
        footer += ' · %s' % user.phone
    if user.email:
        footer += ' · %s' % user.email

    payload = {
        "attachments": [
            {
                "color": "#FAE62D",
                "fallback": "Artist %s created by user %s · %s"
                % (user.artist_name, user.name, user.country),
                "text": "Artist <%s|%s> created by user <%s|%s>"
                % (link, user.artist_name, link, user.name),
                "footer": footer,
            }
        ]
    }
    return send_notification(payload)
