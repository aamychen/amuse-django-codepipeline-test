from unittest import mock
from unittest.mock import call

import responses
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase, override_settings

from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)

from releases.models import Release, RoyaltySplit
from releases.tests.factories import (
    SongFactory,
    RoyaltySplitFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
)

from users.tests.factories import UserFactory, Artistv2Factory


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN, SMART_LINK_MESSAGE_BATCH_SIZE=1)
class SetRoyaltySplitIsOwnerTestCase(TestCase):
    def setUp(self):
        with mock.patch("amuse.tasks.zendesk_create_or_update_user"):
            add_zendesk_mock_post_response()
            self.today = date.today()
            self.tommorow = self.today + timedelta(days=1)
            self.yesterday = self.today - timedelta(days=1)
            self.mock_released_today = ReleaseFactory.create_batch(
                release_date=self.today, status=Release.STATUS_RELEASED, size=10
            )
            self.mock_delivered_release_date_tommorow = ReleaseFactory.create_batch(
                release_date=self.tommorow, status=Release.STATUS_DELIVERED, size=10
            )
            self.mock_released_yesterday = ReleaseFactory.create_batch(
                release_date=self.yesterday, status=Release.STATUS_RELEASED, size=10
            )

    @mock.patch(
        'amuse.services.smart_link.send_smart_link_creation_data_to_link_service'
    )
    @mock.patch('amuse.services.smart_link.create_release_smart_link_message_payload')
    def test_resubmit_smart_link_creation_default_args(
        self,
        create_release_smart_link_message_payload_mock,
        send_smart_link_creation_data_to_link_service_mock,
    ):
        msg_mock = dict(test=True)
        calls = [call(release) for release in self.mock_released_today]
        create_release_smart_link_message_payload_mock.return_value = msg_mock

        call_command("resubmit_smart_link_creation")

        create_release_smart_link_message_payload_mock.assert_has_calls(
            calls, any_order=True
        )
        send_smart_link_creation_data_to_link_service_mock.assert_has_calls(
            [call([msg_mock]) for _ in self.mock_released_today], any_order=True
        )

    @mock.patch(
        'amuse.services.smart_link.send_smart_link_creation_data_to_link_service'
    )
    @mock.patch(
        'amuse.services.smart_link.create_pre_release_smart_link_message_payload'
    )
    def test_resubmit_smart_link_creation_status_delivered(
        self,
        create_pre_release_smart_link_message_payload_mock,
        send_smart_link_creation_data_to_link_service_mock,
    ):
        msg_mock = dict(test=True)
        create_pre_release_smart_link_message_payload_mock.return_value = msg_mock

        call_command("resubmit_smart_link_creation", "--status=DELIVERED")

        create_pre_release_smart_link_message_payload_mock.assert_has_calls(
            [], any_order=True
        )
        send_smart_link_creation_data_to_link_service_mock.assert_has_calls(
            [], any_order=True
        )

    @mock.patch(
        'amuse.services.smart_link.send_smart_link_creation_data_to_link_service'
    )
    @mock.patch('amuse.services.smart_link.create_release_smart_link_message_payload')
    def test_resubmit_smart_link_creation_status_released_date_range_yesterday_tommorow(
        self,
        create_release_smart_link_message_payload_mock,
        send_smart_link_creation_data_to_link_service_mock,
    ):
        msg_mock = dict(test=True)
        create_release_smart_link_message_payload_mock.return_value = msg_mock

        call_command(
            "resubmit_smart_link_creation",
            "--status=RELEASED",
            f"--start-date={self.yesterday}",
            f"--end-date={self.tommorow}",
        )

        releases = self.mock_released_today + self.mock_released_yesterday
        calls = [call(release) for release in releases]

        create_release_smart_link_message_payload_mock.assert_has_calls(
            calls, any_order=True
        )
        send_smart_link_creation_data_to_link_service_mock.assert_has_calls(
            [call([msg_mock]) for _ in releases], any_order=True
        )
