from django.test import TestCase
from releases.tests.factories import ReleaseFactory
from simple_history.manager import HistoryManager
from contenttollgate.models import (
    GenericRelease,
    PendingRelease,
    ApprovedRelease,
    NotApprovedRelease,
    RejectedRelease,
)

PROXY_MODELS = [
    GenericRelease,
    PendingRelease,
    ApprovedRelease,
    NotApprovedRelease,
    RejectedRelease,
]


class ModelTestCase(TestCase):
    def test_release_history_for_proxy_models(self):
        """Inherited proxy model generates history."""

        for proxy_model in PROXY_MODELS:

            class ProxyReleaseFactory(ReleaseFactory):
                class Meta:
                    model = proxy_model

            proxy_release = proxy_model()
            self.assertTrue(isinstance(proxy_release.history, HistoryManager))
            self.assertEqual(proxy_release.history.count(), 0)

            proxy_release = ProxyReleaseFactory()
            self.assertEqual(proxy_release.history.count(), 2)

    def test_release_history_for_proxy_models_shares_history(self):
        release = ReleaseFactory()
        self.assertEqual(release.history.count(), 2)

        i = 0
        for proxy_model in PROXY_MODELS:
            i += 1
            proxied_release = proxy_model.objects.filter(pk=release.pk).first()
            proxied_release.name = 'Name {}'.format(i)
            proxied_release.save()
        self.assertEqual(release.history.count(), 7)
        revisions = release.history.all()
        self.assertEqual(revisions[0].name, 'Name 5')
        self.assertEqual(revisions[1].name, 'Name 4')
        self.assertEqual(revisions[2].name, 'Name 3')
        self.assertEqual(revisions[3].name, 'Name 2')
        self.assertEqual(revisions[4].name, 'Name 1')
