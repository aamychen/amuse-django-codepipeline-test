import json
import logging

import requests
from django.conf import settings
from django.core import exceptions
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from waffle import switch_is_active

from amuse.analytics import royalty_advance_notification
from amuse.services import audiorec, ffwd, lyrics, transcoding, smart_link
from amuse.services.delivery import callback as delivery_callback
from amuse.utils import is_authenticated_http

logger = logging.getLogger(__name__)


class InvalidNotificationTopic(exceptions.ImproperlyConfigured):
    pass


def read_json(request):
    try:
        return json.loads(request.read().decode('utf-8'))
    except ValueError:
        return None


def bad_json_request_response():
    return HttpResponseBadRequest('Could not read JSON from request.')


def invalid_topic_response(topic):
    return HttpResponseNotFound(f"Invalid topic: {topic}")


def is_subscription_confirmation(data):
    return data['Type'] == 'SubscriptionConfirmation'


def is_notification(data):
    return data['Type'] == 'Notification'


def read_topic_arn(data):
    return data["TopicArn"]


def read_message_json(data):
    return json.loads(data['Message'])


def confirm_subscription(data):
    response = requests.get(data['SubscribeURL'])
    response.raise_for_status()
    return HttpResponse('OK')


def response():
    return HttpResponse('OK')


@csrf_exempt
def song_file_transcoder_state_change(request):
    data = read_json(request)
    if not data:
        return bad_json_request_response()

    if is_subscription_confirmation(data):
        return confirm_subscription(data)
    if is_notification(data):
        try:
            transcoding.callback(read_message_json(data))
        except ValueError:
            return bad_json_request_response()
    return response()


@csrf_exempt
def notification(request):
    data = read_json(request)

    if not data:
        logger.warning('SNS message could not be decoded')
        return bad_json_request_response()
    if is_subscription_confirmation(data):
        logger.info('SNS subscription confirmation: %s', data)
        return confirm_subscription(data)
    if is_notification(data):
        try:
            topic = read_topic_arn(data)
            message = read_message_json(data)
            if topic == settings.LYRICS_SERVICE_RESPONSE_TOPIC:
                lyrics.callback(message)
            elif topic == settings.AUDIO_RECOGNITION_SERVICE_RESPONSE_TOPIC:
                audiorec.callback(message)
            elif topic == settings.AUDIO_TRANSCODER_SERVICE_RESPONSE_TOPIC:
                transcoding.callback(message)
            elif topic == settings.FFWD_RECOUP_SNS_TOPIC:
                logger.info('Recoup event with splits: %s', message['split_ids'])
                if switch_is_active(
                    'sns:require_ffwd_recoup_auth'
                ) and not is_authenticated_http(
                    request, settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD
                ):
                    auth_response = HttpResponse(status=status.HTTP_401_UNAUTHORIZED)
                    auth_response['WWW-Authenticate'] = 'Basic'
                    return auth_response

                ffwd.unlock_splits(message['split_ids'])
                logger.info('Unlocked splits: %s', message['split_ids'])
            elif topic == settings.FFWD_NOTIFICATION_SNS_TOPIC:
                royalty_advance_notification(
                    message['user_id'],
                    message['msg_type'],
                    message['total_user_amount'],
                )
            elif topic == settings.SMART_LINK_CALLBACK_SNS_TOPIC:
                if not is_authenticated_http(
                    request, settings.AWS_SNS_USER, settings.AWS_SNS_PASSWORD
                ):
                    auth_response = HttpResponse(status=status.HTTP_401_UNAUTHORIZED)
                    auth_response['WWW-Authenticate'] = 'Basic'
                    return auth_response

                smart_link.amuse_smart_link_callback(message)
            elif topic == settings.RELEASE_DELIVERY_SERVICE_RESPONSE_TOPIC:
                try:
                    delivery_callback.handler(message)
                except exceptions.ObjectDoesNotExist:
                    return HttpResponse(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                logger.warning('Unknown SNS topic %s received %s', topic, message)
                return invalid_topic_response(topic)
        except ValueError:
            logger.warning('Invalid SNS message: %s', data)
            return bad_json_request_response()
    return response()
