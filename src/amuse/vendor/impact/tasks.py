import logging

from amuse.celery import app

from .request import send_request

logger = logging.getLogger(__name__)

MAX_RETRIES = 10


@app.task(bind=True)
def send_impact_event(self, event_id, params):
    try:
        logger.info(
            f'Impact: sending new request, event_id: "{event_id}", params: {str(params)}'
        )

        send_request(event_id, params)
    except Exception as e:
        retries = self.request.retries
        log_func = logger.error if retries == MAX_RETRIES else logger.warning
        msg = f'Impact: error sending request, event_id: "{event_id}", retry: {retries}, exception: {str(e)}'

        log_func(msg)

        # retry strategy with exponential delay (min 60 seconds delay)
        countdown = 60 + 2**self.request.retries
        self.retry(exc=e, countdown=countdown, max_retries=MAX_RETRIES)
