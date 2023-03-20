import pytest

from amuse.platform import PlatformType, PlatformHelper
from payments.models import PaymentTransaction


class MockRequest:
    def __init__(self, user_agent, x_user_agent):
        self.META = {"HTTP_USER_AGENT": user_agent}

        if x_user_agent:
            self.META['HTTP_X_USER_AGENT'] = x_user_agent


@pytest.mark.parametrize(
    "payment_platform, platform_type",
    [
        (PaymentTransaction.PLATFORM_UNKNOWN, PlatformType.UNKNOWN),
        (PaymentTransaction.PLATFORM_ANDROID, PlatformType.ANDROID),
        (PaymentTransaction.PLATFORM_IOS, PlatformType.IOS),
        (PaymentTransaction.PLATFORM_WEB, PlatformType.WEB),
        (PaymentTransaction.PLATFORM_CRON, PlatformType.CRON),
        (PaymentTransaction.PLATFORM_ADMIN, PlatformType.ADMIN),
        (None, PlatformType.UNKNOWN),
    ],
)
def test_from_payment(payment_platform, platform_type):
    payment = PaymentTransaction(platform=payment_platform)
    actual = PlatformHelper.from_payment(payment)
    assert platform_type == actual


@pytest.mark.parametrize(
    "user_agent, x_user_agent, expected",
    [
        ('', '', PlatformType.UNKNOWN),
        ('amuse-android/123;', None, PlatformType.ANDROID),
        ('amuse-ios/123;', None, PlatformType.IOS),
        ('amuse-web/123;', None, PlatformType.WEB),
        ('Mozilla/5.0;', None, PlatformType.UNKNOWN),
        ('Mozilla/5.0;', 'amuse-web/123;', PlatformType.WEB),
    ],
)
def test_from_request(user_agent, x_user_agent, expected):
    request = MockRequest(user_agent, x_user_agent)
    actual = PlatformHelper.from_request(request)
    assert expected == actual
