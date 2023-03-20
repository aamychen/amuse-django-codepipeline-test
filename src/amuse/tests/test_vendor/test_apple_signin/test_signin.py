import responses
import requests

from json import JSONDecodeError

from unittest.mock import patch

from amuse.platform import PlatformType
from amuse.vendor.apple_signin import login
from amuse.vendor.apple_signin.signin import _send_request


class MockResponse:
    def __init__(self, id_token=None):
        self.id_token = id_token
        pass

    def json(self):
        return {"id_token": self.id_token}


@responses.activate
@patch('requests.post')
@patch("jwt.encode", return_value=b"jwt-decoded-abc123")
@patch("base64.b85decode", return_value=b"decoded-abc123")
@patch('amuse.vendor.apple_signin.signin.logger.info')
def test_apple_login_failed_for_invalid_apple_response(
    mock_logger_info, mock_decode, mock_jwt_encode, mock_post
):
    mock_post.return_value = MockResponse()

    authenticated = login(
        platform=PlatformType.IOS, access_token="random-token", apple_signin_id="abc123"
    )

    assert authenticated == False
    assert mock_logger_info.call_count == 1


@responses.activate
@patch('requests.post')
@patch("jwt.decode")
@patch("jwt.encode", return_value=b"jwt-encoded-abc123")
@patch("base64.b85decode", return_value=b"b85-decoded-abc123")
@patch('amuse.vendor.apple_signin.signin.logger.info')
def test_apple_login_success_for_valid_apple_response(
    mock_logger_info, mock_decode, mock_jwt_encode, mock_jwt_decode, mock_post
):
    mock_post.return_value = MockResponse(id_token="fake-id-token")
    mock_jwt_decode.return_value = {"sub": "abc123"}

    authenticated = login(
        platform=PlatformType.IOS, access_token="random-token", apple_signin_id="abc123"
    )

    assert authenticated == True
    assert mock_logger_info.call_count == 1


@responses.activate
@patch('requests.post')
@patch("jwt.decode")
@patch("jwt.encode", return_value=b"jwt-encoded-abc123")
@patch("base64.b85decode", return_value=b"b85-decoded-abc123")
@patch('amuse.vendor.apple_signin.signin.logger.info')
def test_apple_login_success_for_valid_apple_response_web_platform(
    mock_logger_info, mock_decode, mock_jwt_encode, mock_jwt_decode, mock_post
):
    mock_post.return_value = MockResponse(id_token="fake-id-token")
    mock_jwt_decode.return_value = {"sub": "abc123"}

    authenticated = login(
        platform=PlatformType.WEB, access_token="random-token", apple_signin_id="abc123"
    )

    assert authenticated == True
    assert mock_logger_info.call_count == 1


@responses.activate
@patch('requests.post')
@patch("jwt.decode")
@patch("jwt.encode", return_value=b"jwt-encoded-abc123")
@patch("base64.b85decode", return_value=b"b85-decoded-abc123")
@patch('amuse.vendor.apple_signin.signin.logger.info')
def test_apple_login_failed_for_invalid_sub(
    mock_logger_info, mock_decode, mock_jwt_encode, mock_jwt_decode, mock_post
):
    mock_post.return_value = MockResponse(id_token="fake-id-token")
    mock_jwt_decode.return_value = {"sub": "invalid-sub"}

    authenticated = login(
        platform=PlatformType.IOS, access_token="random-token", apple_signin_id="abc123"
    )

    assert authenticated == False
    assert mock_logger_info.call_count == 1


@responses.activate
@patch('amuse.vendor.apple_signin.signin.logger.info')
@patch('amuse.vendor.apple_signin.signin.logger.warning')
@patch('requests.post')
def test_send_request_failed(mock_post, mock_warning, mock_info):
    mock_post.side_effect = requests.exceptions.RequestException()

    response = _send_request(data={}, headers={})
    assert mock_warning.call_count == 1
    assert response == {}
