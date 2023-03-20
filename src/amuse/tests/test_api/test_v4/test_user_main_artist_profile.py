from django.urls import reverse_lazy as reverse
from rest_framework import status

from payments.tests.factories import SubscriptionFactory
from subscriptions.models import SubscriptionPlan
from subscriptions.tests.factories import SubscriptionPlanFactory
from users.tests.factories import UserFactory, Artistv2Factory
from ..base import API_V4_ACCEPT_VALUE, AmuseAPITestCase, API_V3_ACCEPT_VALUE


class UserMainArtistProfileTestCase(AmuseAPITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.artist = self.user.create_artist_v2('artist')

        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(self.user)
        self.url = reverse('user-main-artist-profile')

    def test_main_artist_profile_set(self):
        self.assertIsNone(self.user.main_artist_profile)
        response = self.client.post(self.url, data={'artist_id': self.artist.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self.user.main_artist_profile, self.artist.id)

    def test_main_artist_profile_returned(self):
        self.user.userartistrole_set.update(main_artist_profile=True)
        url = reverse('user-detail', args=[self.user.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['main_artist_profile'], self.artist.pk)

    def test_artist_must_be_part_of_team(self):
        artist = Artistv2Factory()
        response = self.client.post(self.url, data={'artist_id': artist.pk})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_artist_id_missing(self):
        response = self.client.post(self.url, data={'artist_id': self.artist.pk + 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_version_not_supported(self):
        self.client.credentials(HTTP_ACCEPT=API_V3_ACCEPT_VALUE)
        response = self.client.post(self.url, data={'artist_id': self.artist.pk})

        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)

    def test_main_artist_profile_set_already(self):
        self.user.userartistrole_set.update(main_artist_profile=True)
        self.assertTrue(self.user.main_artist_profile, self.artist.pk)

        artist2 = self.user.create_artist_v2('artist 2')
        response = self.client.post(self.url, data={'artist_id': artist2.pk})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pro_user_cannot_set_main_artist_profile(self):
        user = UserFactory(is_pro=True)
        artist = user.create_artist_v2('pro artist')

        response = self.client.post(self.url, data={'artist_id': artist.pk})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_main_artist_profile_reset_on_pro_subscription_purchase(self):
        self.user.userartistrole_set.update(main_artist_profile=True)
        self.assertEqual(self.user.main_artist_profile, self.artist.pk)

        SubscriptionFactory(
            user=self.user, valid_from=self.user.created, plan__trial_days=0
        )
        self.assertIsNone(self.user.main_artist_profile)

    def test_main_artist_profile_kept_on_plus_subscription_purchase(self):
        self.user.userartistrole_set.update(main_artist_profile=True)
        self.assertEqual(self.user.main_artist_profile, self.artist.pk)

        plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PLUS, trial_days=0)
        SubscriptionFactory(user=self.user, valid_from=self.user.created, plan=plan)
        self.assertEqual(self.user.main_artist_profile, self.artist.pk)
