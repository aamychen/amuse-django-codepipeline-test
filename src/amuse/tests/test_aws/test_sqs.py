import json
from unittest import mock
from amuse.vendor.aws import sqs


def test_create_client():
    client = sqs.create_client()
    assert client.__class__.__name__ == "SQS"


@mock.patch("amuse.vendor.aws.sqs.create_client", autospec=True)
def test_send_message_with_queue_name(mock_client):
    queue_name = "foo-bar-baz"
    sqs.send_message(queue_name, "lmao")
    mock_client().create_queue.assert_called_once_with(QueueName=queue_name)


@mock.patch("amuse.vendor.aws.sqs.create_client", autospec=True)
def test_send_message_with_dict(mock_client):
    message = {"foo": "bar"}
    sqs.send_message("foo", message)
    mock_client().send_message.assert_called_once_with(
        QueueUrl=mock_client().create_queue().get.return_value,
        MessageBody=json.dumps(message),
    )


@mock.patch("amuse.vendor.aws.sqs.create_client", autospec=True)
def test_send_message_with_string(mock_client):
    message = "Foo bar"
    sqs.send_message("foo", message)
    mock_client().send_message.assert_called_once_with(
        QueueUrl=mock_client().create_queue().get.return_value, MessageBody=message
    )
