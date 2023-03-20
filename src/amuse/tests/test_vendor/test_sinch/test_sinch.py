from unittest import mock

import pytest
import responses
from amuse.vendor.sinch import send_sms, send_otp_sms, should_use_sinch
from amuse.vendor.sinch.client import Sinch
from django.conf import settings
from waffle.testutils import override_switch


def test_sinch_service_plan_routing_ca():
    client = Sinch()
    client.ca = mock.Mock()
    client.sms("+14165550134", "test")
    client.ca.sms.assert_called_once()


def test_sinch_service_plan_routing_us():
    client = Sinch()
    client.us = mock.Mock()
    client.sms("+15417543010", "test")
    client.us.sms.assert_called_once()


def test_sinch_service_plan_routing_ww():
    client = Sinch()
    client.ww = mock.Mock()
    client.sms("+46701234567", "test")
    client.ww.sms.assert_called_once()


def test_sinch_service_plan_routing_pr_through_us():
    client = Sinch()
    client.us = mock.Mock()
    client.sms("+17871234567", "test")
    client.us.sms.assert_called_once()


@responses.activate
def test_sinch_send_sms():
    endpoint = settings.SINCH_BATCH_API_ENDPOINT % settings.SINCH_WW_SERVICE_PLAN_ID
    responses.add(responses.POST, endpoint, status=201)
    client = Sinch()
    assert client.sms("+46701234567", "test")


@responses.activate
def test_sinch_send_sms_failure():
    endpoint = settings.SINCH_BATCH_API_ENDPOINT % settings.SINCH_WW_SERVICE_PLAN_ID
    responses.add(
        responses.POST, endpoint, json={"code": "failure", "text": "broke"}, status=400
    )
    client = Sinch()
    assert not client.sms("+46701234567", "test")


@pytest.mark.django_db
@override_switch("sinch:active:ww", active=True)
def test_should_use_sinch_with_ww_activated():
    assert should_use_sinch("+15417543010")
    assert should_use_sinch("+46701234567")


@pytest.mark.django_db
@override_switch("sinch:active:ww", active=False)
def test_should_use_sinch_with_ww_deactivated():
    assert not should_use_sinch("+15417543010")
    assert not should_use_sinch("+46701234567")


@pytest.mark.django_db
@override_switch("sinch:active:ww", active=True)
@override_switch("sinch:active:nz", active=False)
def test_should_use_sinch_with_for_nz():
    assert not should_use_sinch("+6412345678")
    assert should_use_sinch("+46701234567")


@mock.patch("amuse.vendor.sinch.client.Client", autospec=True)
def test_send_sms_helper(mock_client):
    send_sms("+123456789", "test")
    mock_client.return_value.sms.assert_called_once_with("+123456789", "test")


@mock.patch("amuse.vendor.sinch.client.Client", autospec=True)
def test_send_otp_sms_helper(mock_client):
    send_otp_sms("+123", "Your Amuse verification code is: 123 456")
    mock_client.return_value.sms.assert_called_once_with(
        "+123", "Your Amuse verification code is: 123 456"
    )


@mock.patch("amuse.vendor.sinch.client.Client", autospec=True)
def test_send_otp_sms_with_hashhelper(mock_client):
    send_otp_sms("+123", "Your Amuse verification code is: 123 456\n\nxyz-hash")
    mock_client.return_value.sms.assert_called_once_with(
        "+123", "Your Amuse verification code is: 123 456\n\nxyz-hash"
    )
