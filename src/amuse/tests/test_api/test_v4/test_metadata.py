from unittest.mock import patch

import grpclib
import pyslayer.exceptions
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class MetadataViewTestCase(APITestCase):
    @patch(
        'amuse.api.base.views.metadata.metadata_spotifyartist',
        return_value={},
        side_effect=pyslayer.exceptions.SlayerRequestError(
            'test-msg', 'test-details', grpclib.Status.INTERNAL
        ),
    )
    def test_artist(self, _):
        url = reverse('metadata-artist')
        response = self.client.post(url, data={'query': 'whatever'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
