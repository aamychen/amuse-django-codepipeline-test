from unittest import mock

from django.test import override_settings

from amuse.vendor.aws import sns


@mock.patch('amuse.vendor.aws.sns.boto3')
def test_sns_create_client(boto3_mock):
    with override_settings(AWS_REGION='us-east-1') as settings:
        sns.sns_create_client()
        boto3_mock.client.assert_called_once_with('sns', region_name='us-east-1')


@mock.patch('amuse.vendor.aws.sns.sns_create_client')
def test_sns_send_message_msg_dict(sns_send_message_mock):
    msg_dict = {'test': 'test'}
    msg_str = '{"test": "test"}'
    client_mock = mock.MagicMock()
    sns_send_message_mock.return_value = client_mock
    sns.sns_send_message('arn:test', msg_dict)
    client_mock.publish.assert_called_once_with(TopicArn='arn:test', Message=msg_str)
