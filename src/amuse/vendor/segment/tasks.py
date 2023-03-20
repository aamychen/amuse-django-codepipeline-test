import logging

from amuse.celery import app
from amuse.vendor.segment import track, identify

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=7, ignore_result=True)
def send_segment_track(self, user_id, event_name, properties=None, context=None):
    try:
        logger.info(
            f'Segment track event {event_name}, '
            f'properties={properties}, '
            f'context={context}'
        )
        track(user_id, event_name, properties=properties, context=context)
    except Exception as e:
        logger.error(
            f'Segment track event error, event={event_name}, '
            f'properties={properties}, '
            f'context={context}',
            f'exception={e}',
        )
        # exponential backoff: 10, 30, 70, 150, 310, 630 seconds
        self.retry(exc=e, countdown=10 * 2**self.request.retries)


@app.task(bind=True, max_retries=7, ignore_result=True)
def send_segment_identify(self, user_id, traits):
    try:
        logger.info(f'Segment identify, traits={traits}')
        identify(user_id, traits)
    except Exception as e:
        logger.error(f'Segment identify error, ' f'traits={traits}, ' f'exception={e}')
        # exponential backoff: 10, 30, 70, 150, 310, 630 seconds
        self.retry(exc=e, countdown=10 * 2**self.request.retries)
