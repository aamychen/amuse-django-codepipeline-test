from unittest import mock

import responses
from django.test import override_settings
from django.urls import reverse_lazy
from rest_framework import status
from rest_framework.exceptions import ValidationError

from amuse.tests.test_api.base import AmuseAPITestCase
from amuse.vendor.twilio.sms import (
    TwilioSMS,
    TwilioException,
    TwilioRestException,
    is_allowed_phone,
    send_sms_code,
    validate_phone,
)
from users.tests.factories import UserFactory

FAKE_MESSAGE_RESPONSE = {
    'account_sid': 'fake-sid',
    'api_version': '2010-04-01',
    'body': 'Download link!',
    'date_created': 'Fri, 11 Jan 2019 10:55:19 +0000',
    'date_updated': 'Fri, 11 Jan 2019 10:55:19 +0000',
    'date_sent': None,
    'direction': 'outbound-api',
    'error_code': None,
    'error_message': None,
    'from': '+46769446877',
    'messaging_service_sid': None,
    'num_media': '0',
    'num_segments': '1',
    'price': None,
    'price_unit': 'USD',
    'sid': 'fake-mess-sid',
    'status': 'queued',
    'to': '+461231212',
    'uri': '/2010-04-01/Accounts/fake-sid/Messages/fake-mess-sid.json',
    'subresource_uris': {
        'media': '/2010-04-01/Accounts/fake-sid/Messages/fake-mess-sid/Media.json'
    },
}


class TwilioSMSIntegrationTestCase(AmuseAPITestCase):
    def setUp(self):
        super().setUp()

        self.twilio_url = (
            'https://api.twilio.com/2010-04-01/Accounts/fake-sid/Messages.json'
        )
        self.user = UserFactory(phone='+4601231212')
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}',
            HTTP_ACCEPT='application/json; version=3',
        )
        responses.add(
            responses.POST, self.twilio_url, status=200, json=FAKE_MESSAGE_RESPONSE
        )

    @responses.activate
    @override_settings(TWILIO_SID='fake-sid', TWILIO_TOKEN='fake-token')
    def test_send_download_link(self):
        url = reverse_lazy('sms-download-link')

        with mock.patch('amuse.vendor.twilio.sms.send_download_link'):
            response = self.client.get(url, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    @responses.activate
    @mock.patch.object(TwilioSMS, 'send')
    def test_send_sms_code(self, mock_twilio):
        message = 'Your Amuse 2FA code is 123 456'

        send_sms_code(self.user.phone, message)
        mock_twilio.assert_called_once_with('+4601231212', message)

    @responses.activate
    def test_is_allowed_phone(self):
        responses.reset()
        responses.add(
            responses.GET,
            'https://lookups.twilio.com/v1/PhoneNumbers/+46700000000?Type=carrier',
            status=200,
            json={
                'caller_name': None,
                'carrier': {
                    'mobile_country_code': '240',
                    'mobile_network_code': '02',
                    'name': 'HI3G Access AB',
                    'type': 'mobile',
                    'error_code': None,
                },
                'country_code': 'SE',
                'national_format': '070-000 00 00',
                'phone_number': '+46700000000',
                'add_ons': None,
                'url': 'https://lookups.twilio.com/v1/PhoneNumbers/+46700000000?Type=carrier',
            },
        )

        country_code, is_allowed = is_allowed_phone('+46700000000')
        assert is_allowed
        assert country_code == 'SE'

    @responses.activate
    def test_is_allowed_canadian_phone(self):
        responses.reset()
        responses.add(
            responses.GET,
            'https://lookups.twilio.com/v1/PhoneNumbers/+1700000000?Type=carrier',
            status=200,
            json={
                'caller_name': None,
                'carrier': {
                    'mobile_country_code': '240',
                    'mobile_network_code': '02',
                    'name': 'Maple Syrup Hockey Puck',
                    'type': None,
                    'error_code': None,
                },
                'country_code': 'CA',
                'national_format': '070-000 00 00',
                'phone_number': '+1700000000',
                'add_ons': None,
                'url': 'https://lookups.twilio.com/v1/PhoneNumbers/+1700000000?Type=carrier',
            },
        )

        country_code, is_allowed = is_allowed_phone('+1700000000')
        assert is_allowed
        assert country_code == 'CA'

    @responses.activate
    @mock.patch.object(TwilioSMS, 'send')
    def test_send_sms_code_handles_twilio_exception(self, mock_twilio):
        mock_twilio.side_effect = TwilioRestException(123, 'fake-uri')

        with self.assertRaises(TwilioException) as context:
            send_sms_code(self.user.phone, '123')

    def test_validate_phone_empty_phone_throws_error(self):
        with self.assertRaises(ValidationError) as context:
            validate_phone('')

        self.assertEqual(context.exception.detail['phone'], 'Invalid phone number')

    def test_validate_phone_none_throws_error(self):
        with self.assertRaises(ValidationError) as context:
            validate_phone(None)

        self.assertEqual(context.exception.detail['phone'], 'Invalid phone number')
