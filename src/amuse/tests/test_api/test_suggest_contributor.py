import responses
from django.urls import reverse_lazy as reverse

from releases.models import SongArtistRole
from releases.tests.factories import SongArtistRoleFactory, SongFactory, ReleaseFactory
from users.tests.factories import UserFactory, Artistv2Factory
from .base import AmuseAPITestCase


class ReleaseAPITestCase(AmuseAPITestCase):
    def setUp(self):
        super(ReleaseAPITestCase, self).setUp()

        self.user = UserFactory(artist_name='Big Cat')
        self.artistV2 = self.user.create_artist_v2(name='Big Cat')

        self.client.credentials(
            HTTP_AUTHORIZATION='Token ' + self.user.auth_token.key,
            HTTP_ACCEPT='application/json; version=2',
        )

        self.release = ReleaseFactory(user=self.user, created_by=self.user)
        self.song = SongFactory(release=self.release)

        SongArtistRoleFactory(
            song=self.song,
            artist=Artistv2Factory(name="FeaturedArtist"),
            role=SongArtistRole.ROLE_FEATURED_ARTIST,
        )
        SongArtistRoleFactory(
            song=self.song,
            artist=Artistv2Factory(name="MrWriter"),
            role=SongArtistRole.ROLE_WRITER,
        )
        SongArtistRoleFactory(
            song=self.song,
            artist=Artistv2Factory(name="MrProducer"),
            role=SongArtistRole.ROLE_PRODUCER,
        )
        SongArtistRoleFactory(
            song=self.song,
            artist=Artistv2Factory(name="MrMixer"),
            role=SongArtistRole.ROLE_MIXER,
        )
        SongArtistRoleFactory(
            song=self.song,
            artist=Artistv2Factory(name="MrREMixer"),
            role=SongArtistRole.ROLE_REMIXER,
        )

    @responses.activate
    def test_sugest_contributor(self):
        suggest_url = reverse('suggest-contributor')
        response = self.client.get(suggest_url)

        suggest_list = response.data['contributors']
        self.assertTrue(any(d['name'] == 'FeaturedArtist' for d in suggest_list))
        self.assertTrue(any(d['name'] == 'MrWriter' for d in suggest_list))
        self.assertTrue(any(d['name'] == 'MrProducer' for d in suggest_list))
        self.assertTrue(any(d['name'] == 'MrMixer' for d in suggest_list))
        self.assertTrue(any(d['name'] == 'MrREMixer' for d in suggest_list))
