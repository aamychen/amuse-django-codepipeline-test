import logging

import json
import base64
from amuse.settings.constants import GCP_PUBSUB_PUBLISH_TIMEOUT
from django.conf import settings
from google.auth import jwt
from google.cloud import pubsub_v1
from concurrent import futures

logger = logging.getLogger(__name__)


class PubSubAuthenticationError(Exception):
    pass


class PubSubPublishError(Exception):
    pass


class PubSubClient:
    def authenticate(self):
        try:
            service_account_info = json.loads(
                base64.b85decode(settings.GCP_SERVICE_ACCOUNT_JSON).decode('UTF-8')
            )
            audience = "https://pubsub.googleapis.com/google.pubsub.v1.Publisher"
            credentials = jwt.Credentials.from_service_account_info(
                service_account_info, audience=audience
            )
            credentials_pub = credentials.with_claims(audience=audience)
            self.publisher = pubsub_v1.PublisherClient(credentials=credentials_pub)
            self.project_id = "amuse-data-analytics"

        except Exception as e:
            raise PubSubAuthenticationError(f'Authentication to GCP failed with: {e}')

    def __init__(self, topic_id):
        self.authenticate()
        self.topic_id = topic_id

    def publish(self, message):
        """Publishes multiple messages to a Pub/Sub topic with an error handler."""

        publish_timeout = GCP_PUBSUB_PUBLISH_TIMEOUT
        topic_path = self.publisher.topic_path(self.project_id, self.topic_id)
        data = message
        # When you publish a message, the client returns a future.
        publish_future = self.publisher.publish(topic_path, data.encode("utf-8"))
        try:
            res = publish_future.result(publish_timeout)
            logger.info(
                f"Published message: {message} to {topic_path}. with result: {res}"
            )
        except Exception as e:
            raise PubSubPublishError(
                f'Publishing message: {message} to topic path: {topic_path} failed with error: {e}'
            )
