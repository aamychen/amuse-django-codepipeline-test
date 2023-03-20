from django.http import HttpResponse
from sentry_sdk import configure_scope

from releases.models import Genre


def healthcheck(request):
    # Do not trace this endpoint in Sentry
    with configure_scope() as scope:
        if scope.transaction:
            scope.transaction.sampled = False

    Genre.objects.first()
    Genre.objects.using('replica').first()

    return HttpResponse()
