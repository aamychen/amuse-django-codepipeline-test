import boto3
import json
from django.conf import settings


def create_client():
    return boto3.client("sqs", region_name=settings.AWS_REGION)


def send_message(queue, message):
    if type(message) is not str:
        message = json.dumps(message)
    client = create_client()
    queue = client.create_queue(QueueName=queue)
    return client.send_message(QueueUrl=queue.get("QueueUrl"), MessageBody=message)
