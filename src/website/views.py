import logging
from django.shortcuts import redirect, render
from django.contrib.gis.geoip2 import GeoIP2

log = logging.getLogger(__name__)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def index(request):
    launched = False
    ip = get_client_ip(request)
    if 'ip' in request.GET:
        ip = request.GET.get('ip')
    try:
        geoip = GeoIP2()
        country = geoip.country(ip)
        launched = country.get('country_code') in ('GH', 'KE')
    except Exception as e:
        log.exception(e)
    return render(request, 'website/index.html', {'launched': launched})


def privacy(request):
    return redirect('/ext-legal-agreements/', True)


def ext_legal_agreements(request):
    return render(request, 'website/ext_legal_agreements.html')
