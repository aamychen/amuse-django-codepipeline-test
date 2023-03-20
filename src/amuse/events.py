from amuse.models.event import Event
from amuse.utils import get_ip_address, parse_client_version


def created(request, obj):
    client, version = parse_client_version(request.META.get('HTTP_USER_AGENT') or '')
    ip = get_ip_address(request)
    return Event.objects.create(
        type=Event.TYPE_CREATE, client=client, version=version, object=obj, ip=ip
    )
