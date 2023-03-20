from apidocs.views import OpenAPIBaseView
from rest_framework import status
from rest_framework.reverse import reverse
from users.tests.factories import UserFactory
from amuse.tests.test_api.base import AmuseAPITestCase

VERSION_LATEST = OpenAPIBaseView.versioning_class.default_version


class OpenAPITest(AmuseAPITestCase):
    def setUp(self):
        self.user_admin = UserFactory(is_staff=True)
        self.user_normal = UserFactory(is_staff=False)
        self.client.force_login(user=self.user_admin)
        self.url_base = reverse('oas-base')
        self.url_redoc = reverse('oas-redoc')
        self.url_swagger = reverse('oas-swagger')

    def test_schema_base_versioned(self):
        version_in = 2
        resp = self.client.get(self.url_base, {'version': version_in})
        version_out = int(resp.data['info']['version'])
        self.assertEqual(version_in, version_out)

    def test_schema_base_version_default(self):
        resp = self.client.get(self.url_base)
        version_out = int(resp.data['info']['version'])
        self.assertEqual(version_out, VERSION_LATEST)

    def test_schema_base_forbidden(self):
        self.client.force_login(user=self.user_normal)
        resp = self.client.get(self.url_base)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_schema_redoc_forbidden(self):
        self.client.force_login(user=self.user_normal)
        resp = self.client.get(self.url_redoc)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_schema_redoc_versioned(self):
        version_in = 3
        resp = self.client.get(self.url_redoc, {'version': version_in})
        schema_url_versioned = '%s?version=%s' % (self.url_base, version_in)
        self.assertEqual(resp.data['schema_url'], schema_url_versioned)

    def test_schema_redoc_version_default(self):
        resp = self.client.get(self.url_redoc)
        schema_url_versioned = '%s?version=%s' % (self.url_base, VERSION_LATEST)
        self.assertEqual(resp.data['schema_url'], schema_url_versioned)

    def test_schema_swagger_versioned(self):
        version_in = 5
        resp = self.client.get(self.url_swagger, {'version': version_in})
        schema_url_versioned = '%s?version=%s' % (self.url_base, version_in)
        self.assertEqual(resp.data['schema_url'], schema_url_versioned)

    def test_schema_swagger_version_default(self):
        resp = self.client.get(self.url_swagger)
        schema_url_versioned = '%s?version=%s' % (self.url_base, VERSION_LATEST)
        self.assertEqual(resp.data['schema_url'], schema_url_versioned)
