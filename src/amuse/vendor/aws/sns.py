import boto3
import json
from django.conf import settings


def sns_create_client():
    return boto3.client("sns", region_name=settings.AWS_REGION)


def sns_send_message(topic_arn, message):
    if type(message) is not str:
        message = json.dumps(message)
    client = sns_create_client()
    return client.publish(TopicArn=topic_arn, Message=message)
