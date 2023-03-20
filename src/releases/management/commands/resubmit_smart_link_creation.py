from typing import Optional

from django.conf import settings
from datetime import date

from dateutil.parser import isoparse
from django.core.management.base import BaseCommand

from amuse.utils import chunks
from releases.models import Release
from amuse.services import smart_link


class Command(BaseCommand):
    help = """
    Resubmits smart link creation messages for Releases.
    By default it resubmits RELEASED Releases that are released today.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=isoparse,
            help='Release date starting from this date. Example: 2019-01-01',
        )
        parser.add_argument(
            '--end-date',
            type=isoparse,
            help='Release date up until this date. Example: 2019-12-31',
        )
        parser.add_argument(
            '--status',
            help='Release status. Valid options are either RELEASED or DELIVERED.',
        )

    def get_func_for_msg_creation(self, release_status):
        return {
            Release.STATUS_RELEASED: smart_link.create_release_smart_link_message_payload,
            Release.STATUS_DELIVERED: smart_link.create_pre_release_smart_link_message_payload,
        }[release_status]

    def parse_status(self, status: Optional[str]):
        if not status:
            return Release.STATUS_RELEASED

        status = status.upper().strip()
        return {
            'RELEASED': Release.STATUS_RELEASED,
            'DELIVERED': Release.STATUS_DELIVERED,
        }[status]

    def handle(self, *args, **kwargs):
        """
        We fetch all releases with given status between the given dates,
        create smart link creation messages and resubmit them over the SNS.
        In case `status` is not provided we default to `RELEASED` status.
        In case `start_date` or `end_date` are not provided, we default to today.
        """
        start_date = kwargs.get('start_date', None)
        end_date = kwargs.get('end_date', None)
        status = kwargs.get('status', None)
        status = self.parse_status(status)
        filter_kwargs = dict(status=status)

        if not start_date or not end_date:
            filter_kwargs['release_date'] = date.today()

        if start_date and end_date:
            filter_kwargs['release_date__gte'] = start_date
            filter_kwargs['release_date__lte'] = end_date

        msg_creation_func = self.get_func_for_msg_creation(status)
        releases = Release.objects.filter(**filter_kwargs)
        messages = [msg_creation_func(release) for release in releases]
        for message_batch in chunks(messages, settings.SMART_LINK_MESSAGE_BATCH_SIZE):
            smart_link.send_smart_link_creation_data_to_link_service(message_batch)
