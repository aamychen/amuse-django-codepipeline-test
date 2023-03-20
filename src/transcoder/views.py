import json
import logging
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from transcoder.signals import (
    transcoder_progress,
    transcoder_complete,
    transcoder_error,
)

logger = logging.getLogger(__name__)


@csrf_exempt
def callback(request):
    try:
        data = json.loads(request.read().decode('utf-8'))
    except ValueError:
        return HttpResponseBadRequest('Invalid JSON')

    if data['Type'] == 'SubscriptionConfirmation':
        logger.error('Subscription URL: {0}'.format(data['SubscribeURL']))
        return HttpResponse('OK')

    try:
        message = json.loads(data['Message'])
    except ValueError:
        assert False, data['Message']

    if message['state'] == 'PROGRESSING':
        transcoder_progress.send(sender=None, message=message)
    elif message['state'] == 'COMPLETED':
        transcoder_complete.send(sender=None, message=message)
    elif message['state'] == 'ERROR':
        transcoder_error.send(sender=None, message=message)

    return HttpResponse('OK')
