from datetime import datetime
import time

from requests import Session
from requests.auth import HTTPBasicAuth
from requests.exceptions import ReadTimeout
from django.conf import settings
from django.core.management import BaseCommand
from users.models import User


class Command(BaseCommand):
    help = """
    WARNING: RUN THIS ONLY IF YOU KNOW WHAT YOU ARE DOING.
    The command iterates through db users from user_id=max_user_id to user_id=min_user_id (in descending order).
    The command use "CustomerIO Beta API" and "CustomerIO The Behavioral Tracking API".
    Beta API is used to fetch CustomerIO users.
    The Behavioral Tracking API is used to delete invalid devices.
    Due to CustomerIO rate limits, the code is purposely "slow".
    Device is considered as "invalid" if device_id length is less than 100 characters.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--test_mode',
            dest='test_mode',
            type=bool,
            default=False,
            help='Just print, do not update',
        )
        parser.add_argument(
            '--max_user_id',
            dest='max_user_id',
            type=int,
            default=0,
            help='An integer user id to start the update from',
        )
        parser.add_argument(
            '--min_user_id',
            dest='min_user_id',
            type=int,
            default=0,
            help='The last id of users being processed',
        )

    def handle(self, *args, **kwargs):
        test_mode = kwargs.get('test_mode')
        max_user_id = kwargs.get('max_user_id')
        min_user_id = kwargs.get('min_user_id')

        if max_user_id <= min_user_id:
            raise Exception("Max max_user_id has to be greater than min_user_id")

        start_time = datetime.now()
        user_batch_size = 10
        total_invalid_tokens = 0

        info(0, "Running clean_invalid_customerio_devices command...")
        info(0, "Test mode: ", test_mode)
        info(0, "Start time:", start_time)
        info(0, "Max User ID:", max_user_id)

        cio = CIO(
            site_id=settings.CUSTOMERIO_SITE_ID, api_key=settings.CUSTOMERIO_API_KEY
        )

        batch = 0
        while max_user_id > min_user_id:
            info(
                1,
                f"Fetching batch of users, batch={batch}, max_user_id={max_user_id}, "
                f"batch_size={user_batch_size}",
            )

            user_ids = list(
                User.objects.values_list('id', flat=True)
                .order_by('-id')
                .filter(id__lte=max_user_id, id__gte=min_user_id)
            )[0:user_batch_size]

            user_ids = [str(user_id) for user_id in user_ids]

            info(2, f'Get customer attributes, ids:', user_ids)
            customers = cio.get_customer_attributes(user_ids)

            devices = self.find_invalid_device_ids(customers)
            total_invalid_tokens += len(devices)
            self.delete_devices(test_mode, cio, devices)

            info(1, f'Batch Completed')
            self.progres_report(start_time, batch, total_invalid_tokens)

            batch += 1
            max_user_id = self.next_max_user_id(user_ids)
            self.delay()

        info(0, "...completed clean_invalid_customerio_devices command!")
        self.progres_report(start_time, batch, total_invalid_tokens)

    @staticmethod
    def progres_report(start_time, batch, total_invalid_devices):
        end_time = datetime.now()
        elapsed = end_time - start_time

        info(
            0,
            f"Elapsed: {str(elapsed)}, "
            f"batch: {batch}, "
            f"total_invalid_devices: {total_invalid_devices}",
        )
        info(0, f'======================================')

    @staticmethod
    def delay():
        # Customer.io rate limits:
        # - track.customer.io have fair use rate limit of 100/requests per second
        # - api.customer.io and beta-api.customer.io are hard limited to 10/rps
        # More: https://customer.io/docs/api/#api-documentationlimits
        time.sleep(0.5)

    @staticmethod
    def delete_devices(test_mode, cio, devices):
        if len(devices) == 0:
            return

        info(2, f'Start processing devices...')
        for device in devices:
            cid = device['customer_id']
            did = device['device_id']
            info(3, f'Removing device: customer_id={cid}, device_id={did}')

            if not test_mode:
                cio.delete_device(cid, did)
        info(2, f'Device processing completed...')

    def find_invalid_device_ids(self, customers):
        info(2, f'Find invalid devices')

        invalid_tokens = []
        if 'customers' not in customers:
            return invalid_tokens

        for customer in customers['customers']:
            cid = customer['id']

            devices = customer['devices']
            if not devices:
                continue

            for device in devices:
                device_id = device['id']
                if not self.is_valid_token(device_id):
                    invalid_tokens.append({'customer_id': cid, 'device_id': device_id})

        if len(invalid_tokens) == 0:
            info(2, f'Invalid devices not found')

        return invalid_tokens

    @staticmethod
    def is_valid_token(token):
        # Valid firebase tokens are usually longer than 100 chars (in amuse prod db
        # there are valid tokens with length of 152, 163, and 174 characters).
        # Invalid tokens are usually much shorter than 100 chars.
        return len(token) > 100

    @staticmethod
    def next_max_user_id(user_ids):
        if len(user_ids) == 0:
            return 0

        last_id = user_ids[len(user_ids) - 1]

        return int(last_id) - 1


class CIO:
    def __init__(self, site_id=None, api_key=None, retries=3, timeout=10):
        if api_key is None or site_id is None:
            raise CIOException('CustomerIO credentials are not provided')

        self.site_id = site_id
        self.api_key = api_key
        self.retries = retries
        self.timeout = timeout

        self.http = Session()
        self.auth = HTTPBasicAuth(site_id, api_key)

    def get_customer_attributes(self, ids: list):
        url = 'https://beta-api.customer.io/v1/api/customers/attributes'
        data = {'ids': ids}

        return self.send_request('POST', url, data)

    def delete_device(self, customer_id, device_id):
        url = f'https://track.customer.io/api/v1/customers/{str(customer_id)}/devices/{device_id}'
        self.send_request('DELETE', url, {})

    def send_request(self, method, url, data, retry_counter=0):
        try:
            headers = {'content-type': 'application/json'}
            response = self.http.request(
                method,
                url=url,
                json=data,
                auth=self.auth,
                headers=headers,
                timeout=self.timeout,
            )
        except ReadTimeout as e:
            # This is a long-running-job, and every few hours we will receive ReadTimeOutError from CustomerIO (probably due to CustomerIO deployments or). Usually, CustomerIO is available few minutes after the error.
            info(1, "ReadTimeoutError", e)
            if retry_counter < 20:
                return self.try_to_recovery(method, url, data, retry_counter)
            raise CIOException(
                f'Was not able to self recover after {retry_counter} tries.'
            )
        except Exception as e:
            raise CIOException(e)
        result_status = response.status_code
        if result_status != 200:
            raise CIOException('%s: %s %s' % (result_status, url, data))

        return response.json()

    def try_to_recovery(self, method, url, data, retry_counter):
        """Wait 2 minutes and try to send request again."""
        wait_seconds = 120
        step_seconds = 5
        elapsed_seconds = 0

        while elapsed_seconds < wait_seconds:
            info(
                4, f' -> will try to self recover in {wait_seconds - elapsed_seconds}s'
            )
            time.sleep(step_seconds)
            elapsed_seconds += step_seconds

        info(2, "Self recovering...")
        return self.send_request(method, url, data, retry_counter + 1)


class CIOException(Exception):
    pass


def info(lvl=0, *args):
    prefix = '' if lvl == 0 else str.rjust(' ', lvl)
    print(prefix, *args)
