import functools

from django.core.cache import cache

from .enums import ProcessingResult
from .helpers import info


class DuplicateNotificationChecker(object):
    """
    Sometimes google sends exact the same notification multiple times.
    This code stores notification id (message_id) to the cache (for 1 day) and ensures
    that notification is not processed multiple times.
    """

    PROCESSING = 1
    PROCESSED = 2
    PROCESSING_TIMEOUT = 60
    PROCESSED_TIMEOUT = 86400

    def __init__(self, payload):
        self.cache_key = f'GOOGLE_BILLING_{payload["message"]["message_id"]}'
        self.value = cache.get(self.cache_key)

    def is_processed(self):
        return self.value == self.PROCESSED

    def is_processing(self):
        return self.value == self.PROCESSING

    def set_processed(self):
        self.value = self.PROCESSED
        cache.set(self.cache_key, value=self.PROCESSED, timeout=self.PROCESSED_TIMEOUT)

    def set_processing(self):
        self.value = self.PROCESSING
        cache.set(
            self.cache_key, value=self.PROCESSING, timeout=self.PROCESSING_TIMEOUT
        )

    def clear(self):
        self.value = None
        cache.delete(self.cache_key)


def check_duplicate_notifications(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        event_id = args[0]._event_id
        payload = args[1]
        checker = DuplicateNotificationChecker(payload)

        mid = payload["message"]["message_id"]
        if checker.is_processing():
            info(event_id, f'Duplicate notification, already processing. Fail. {mid}')
            return ProcessingResult.FAIL

        if checker.is_processed():
            info(event_id, f'Duplicate notification, already processed. Success. {mid}')
            return ProcessingResult.SUCCESS

        try:
            checker.set_processing()
            result = func(*args, **kwargs)

            if result == ProcessingResult.SUCCESS:
                checker.set_processed()

            if result == ProcessingResult.FAIL:
                checker.clear()

            return result
        except Exception as e:
            # clear the cache, but re-throw the exception
            checker.clear()
            raise e

    return wrapper
