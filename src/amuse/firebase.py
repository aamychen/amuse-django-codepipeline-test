import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model


def send_notification(user, message):
    headers = {'Authorization': 'key={0}'.format(settings.FIREBASE_API_SERVER_KEY)}
    payload = {'to': user.firebase_token, 'notification': {'body': message}}
    return requests.post(settings.FIREBASE_API_URL, headers=headers, json=payload)


@csrf_exempt
def slack_notification(request):
    try:
        User = get_user_model()
        email, message = request.POST.get('text').split(maxsplit=1)
        send_notification(User.objects.get(email=email), message)
        return HttpResponse('OK')
    except:
        return HttpResponseBadRequest('Invalid POST')
