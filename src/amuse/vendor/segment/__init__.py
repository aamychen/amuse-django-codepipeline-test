from django.conf import settings
from .version import VERSION
from .client import Client

__version__ = VERSION

"""Settings."""
host = None
on_error = None
debug = False
send = True

default_client = None


def track(*args, **kwargs):
    """Send a track call."""
    _proxy('track', *args, **kwargs)


def identify(*args, **kwargs):
    """Send a identify call."""
    _proxy('identify', *args, **kwargs)


def flush():
    """Tell the client to flush."""
    _proxy('flush')


def _proxy(method, *args, **kwargs):
    """Create an segment analytics client if one doesn't exist and send to it."""
    global default_client
    if not default_client:
        write_key = settings.SEGMENT_WRITE_KEY
        default_client = Client(
            write_key, host=host, debug=debug, on_error=on_error, send=send
        )

    fn = getattr(default_client, method)
    fn(*args, **kwargs)
