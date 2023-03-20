import logging

from amuse.celery import app

from .request import send_request

logger = logging.getLogger(__name__)


@app.task(bind=True, ignore_result=True)
def send_event(self, event_id, url, data, headers={}):
    event_name = data.get('eventName')
    try:
        logger.info(
            f'AppsFlyer: sending new request, event_id: "{event_id}", event_name: "{event_name}"'
        )

        send_request(event_id, url, data, headers)
    except Exception as e:
        logger.error(
            f'AppsFlyer: error sending request, event_id: "{event_id}", event_name: "{event_name}", exception: {str(e)}'
        )
        self.retry(exc=e, countdown=60, max_retries=5)
