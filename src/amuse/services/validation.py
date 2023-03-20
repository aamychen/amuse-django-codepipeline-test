import json

from django.conf import settings
from waffle import switch_is_active

from amuse.logging import logger
from amuse.services.delivery.encoder import release_json
from amuse.vendor.gcp import pubsub


def validate(release):
    if switch_is_active("service:validation:gcp"):
        trigger_gcp_validation_service(release)


def trigger_gcp_validation_service(release):
    try:
        payload = release_json(release, check_empty_checksum=False)
        publisher = pubsub.PubSubClient(settings.PUBSUB_RELEASE_VALIDATION_TOPIC)
        publisher.publish(json.dumps(payload))
    except Exception as e:
        logger.exception(e)
