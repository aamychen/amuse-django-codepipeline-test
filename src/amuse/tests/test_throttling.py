from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase, RequestFactory

from amuse.throttling import LoginEndpointThrottle


class LoginThrottleTestCase(TestCase):
    def setUp(self):
        cache.clear()

        self.allowed_requests = 3

        self.throttler = LoginEndpointThrottle()
        self.throttler.num_requests = self.allowed_requests
        self.throttler.duration = 1
        self.throttler.block_time_seconds = 30

        self.set_throttle_timer(0)

    def test_long_block_throttle(self):
        request = RequestFactory().get('/noop')
        request.user = AnonymousUser()

        for dummy in range(self.allowed_requests):
            assert self.throttler.allow_request(request, None) is True

        assert (
            self.throttler.allow_request(request, None) is False
        ), 'Should have been blocked by the regular rate limit'

        # Advance the timer until the regular rate limit has no effect
        self.set_throttle_timer(self.throttler.duration)

        assert (
            self.throttler.allow_request(request, None) is False
        ), 'Should have been blocked by the longer duration'

        self.set_throttle_timer(self.throttler.block_time_seconds + 1)

        assert self.throttler.allow_request(request, None) is True

    def test_allow_ip_in_white_list(self):
        request = RequestFactory().get('/noop')
        request.META['REMOTE_ADDR'] = '217.31.163.186'
        request.user = AnonymousUser()

        with self.settings(IP_WHITE_LIST_THROTTLE=['217.31.163.186']):
            for dummy in range(self.allowed_requests):
                assert self.throttler.allow_request(request, None) is True
            assert self.throttler.allow_request(request, None) is True

    def set_throttle_timer(self, value):
        self.throttler.timer = lambda: value
