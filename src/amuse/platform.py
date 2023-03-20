import enum

from .utils import (
    parse_client_version,
    CLIENT_OTHER,
    CLIENT_WEB,
    CLIENT_ANDROID,
    CLIENT_IOS,
)


class PlatformType(enum.IntEnum):
    UNKNOWN = 0
    ANDROID = 1
    IOS = 2
    WEB = 3
    CRON = 4
    ADMIN = 5


class PlatformHelper(object):
    @staticmethod
    def from_request(request):
        cv = parse_client_version(request.META.get('HTTP_USER_AGENT', ''))
        if cv[0] == CLIENT_OTHER and 'HTTP_X_USER_AGENT' in request.META:
            cv = parse_client_version(request.META.get('HTTP_X_USER_AGENT'))

        mapper = {
            CLIENT_IOS: PlatformType.IOS,
            CLIENT_WEB: PlatformType.WEB,
            CLIENT_ANDROID: PlatformType.ANDROID,
        }

        client_version = cv[0]
        return mapper.get(client_version, PlatformType.UNKNOWN)

    @staticmethod
    def from_payment(payment):
        if not payment.platform:
            return PlatformType.UNKNOWN

        return PlatformType(payment.platform)
