import logging
import time
from datetime import date

import tablib
from django.core.management.base import BaseCommand

from amuse.vendor.hyperwallet.client import get_payments

logger = logging.getLogger(__name__)
logging.getLogger("amuse.vendor.hyperwallet").setLevel(logging.WARNING)
HEADERS = (
    "token",
    "status",
    "createdOn",
    "amount",
    "currency",
    "clientPaymentId",
    "purpose",
    "expiresOn",
    "destinationToken",
    "programToken",
)


class Command(BaseCommand):
    help = """
    Make API calls to the payments Hyperwallet API endpoints to get batches with 100
    results. There's an API GET rate limit for 5 requests per second and 7,500
    requests per hour so we throttle requests to stay under that limit.

    The output will be written to a file incrementally.

    https://docs.hyperwallet.com/content/api/v3/resources/payments/list
    """

    def add_arguments(self, parser):
        parser.add_argument('--start-date', type=str, help='2019-01-01')
        parser.add_argument('--end-date', type=str, help='2019-12-31')
        parser.add_argument(
            '--limit', type=int, default=100, help='Items to retrieve per request'
        )

    def handle(self, *args, **kwargs):
        start_date = kwargs.get('start_date', None)
        end_date = kwargs.get('end_date', None)
        limit = kwargs.get('limit')
        delay = 0.6
        offset, count = 0, 0
        file_format = "csv"

        assert start_date and end_date and limit <= 100

        file_name = "/tmp/hyperwallet_report_%s_%s.%s" % (
            start_date,
            end_date,
            file_format,
        )
        create_initial_file(file_name, file_format)

        print("Created %s" % file_name)

        # 7,500 requests per hour is 2.08 requests/sec and we need to reserve some
        # quota for regular GET requests so 0.6 delay is max 1.66 calls per second with
        # an hourly max of 6,000 calls that leaves a 1,500 buffer.
        while True:
            payment_data = get_payments(start_date, end_date, limit, offset)

            # The API returns a 204 when there are no more results
            if payment_data is None:
                break

            count = payment_data["count"]

            print(
                "Processing items %s-%s of a total of %s items"
                % (offset, offset + limit, count)
            )

            with open(file_name, "a+") as f:
                data = tablib.Dataset()

                for entry in payment_data["data"]:
                    values = [entry.get(key) for key in HEADERS]
                    data.append(values)

                f.write(data.export(file_format))

            time.sleep(delay)

            offset += limit

        print("Finished processing %s items for %s" % (count, file_name))


def create_initial_file(file_name, file_format):
    """Creates if it doesn't exist"""
    data = tablib.Dataset(headers=HEADERS)

    with open(file_name, "w+") as f:
        f.write(data.export(file_format))
