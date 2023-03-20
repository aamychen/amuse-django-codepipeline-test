import responses
from django.test import TestCase, override_settings
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)
from releases.models import SongArtistRole
from contenttollgate.blacklist import find_offending_words, find_offending_artists
from users.tests.factories import Artistv2Factory, UserFactory

from releases.tests.factories import (
    ReleaseFactory,
    SongFactory,
    SongArtistRoleFactory,
    ReleaseArtistRoleFactory,
)

from releases.models import ReleaseArtistRole, BlacklistedArtistName


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class AdminBlacklistTestCase(TestCase):
    @responses.activate
    def setUp(self):
        add_zendesk_mock_post_response()
        """
        Setting up 5 users & artists that contribute to each others songs in different ways.

        Comments on expected outcomes based on these mocks in respective tests.
        """
        self.user1 = UserFactory(first_name="Ed Sheeran")
        self.artist1 = Artistv2Factory(name=self.user1.first_name, owner=self.user1)
        BlacklistedArtistName.objects.create(name='Ed Sheeran')

        self.user2 = UserFactory(first_name="Lynyrd Skynyrd")
        self.artist2 = Artistv2Factory(name=self.user2.first_name, owner=self.user2)
        BlacklistedArtistName.objects.create(name='Lynyrd Skynyrd')

        self.user3 = UserFactory(first_name="Test_User")
        self.artist3 = Artistv2Factory(name="The Whitelisted", owner=self.user3)

        self.user4 = UserFactory(first_name="Sam", last_name="Smith")
        self.artist4 = Artistv2Factory(name="Sam Smith", owner=self.user4)
        BlacklistedArtistName.objects.create(name='Sam Smith')

        self.user5 = UserFactory(first_name="I WRITE", last_name="WRITER")
        self.artist5 = Artistv2Factory(name="MasterWriter", owner=self.user5)

        self.release = ReleaseFactory(name="Releasing my tests", user=self.user1)
        ReleaseArtistRoleFactory(release=self.release, artist=self.artist1)

        ReleaseArtistRoleFactory(
            release=self.release,
            artist=self.artist3,
            role=ReleaseArtistRole.ROLE_FEATURED_ARTIST,
            main_primary_artist=False,
        )

        self.song1 = SongFactory(release=self.release, name='Tidal Wave')
        self.song2 = SongFactory(release=self.release, name='C-oldplay')
        self.song3 = SongFactory(release=self.release, name='Dreaming')

        self.release2 = ReleaseFactory(
            name="Remix Single of Sam Smith", user=self.user3
        )
        ReleaseArtistRoleFactory(release=self.release2, artist=self.artist3)

        self.song4 = SongFactory(release=self.release2, name="Remix of a Song")

        SongArtistRoleFactory(artist=self.artist1, song=self.song1)
        SongArtistRoleFactory(
            artist=self.artist2, song=self.song1, role=SongArtistRole.ROLE_MIXER
        )

        SongArtistRoleFactory(
            artist=self.artist3, song=self.song1, role=SongArtistRole.ROLE_WRITER
        )

        SongArtistRoleFactory(
            artist=self.artist1,
            song=self.song2,
            role=SongArtistRole.ROLE_FEATURED_ARTIST,
        )

        SongArtistRoleFactory(
            artist=self.artist4, song=self.song2, role=SongArtistRole.ROLE_WRITER
        )

        SongArtistRoleFactory(
            artist=self.artist3,
            song=self.song2,
            role=SongArtistRole.ROLE_PRIMARY_ARTIST,
        )

        SongArtistRoleFactory(artist=self.artist1, song=self.song3)
        SongArtistRoleFactory(
            artist=self.artist2, song=self.song3, role=SongArtistRole.ROLE_WRITER
        )

        SongArtistRoleFactory(
            artist=self.artist3, song=self.song3, role=SongArtistRole.ROLE_MIXER
        )

        SongArtistRoleFactory(artist=self.artist3, song=self.song4)
        SongArtistRoleFactory(
            artist=self.artist2, song=self.song4, role=SongArtistRole.ROLE_REMIXER
        )

        SongArtistRoleFactory(
            artist=self.artist1, song=self.song4, role=SongArtistRole.ROLE_PRODUCER
        )

        SongArtistRoleFactory(
            artist=self.artist5, song=self.song4, role=SongArtistRole.ROLE_WRITER
        )

    def test_find_blacklisted_word_on_release(self):
        """
        Tests that find_offending_words() returns all the blacklisted
        artists (Primary, featured, remixer & producer) in a release.

        It also tests that it properly exclude song titles, and artists that isn't black listed.

        """
        matches = find_offending_words(self.release)
        # Ed Sheeran is primary/featured and blacklisted
        # and should be in matches-list
        self.assertIn(('Ed Sheeran', 'Ed Sheeran'), matches)

        # M.I.A. is only ROLE_OTHER, WRITER and therefore
        # not in matches-list even though blacklisted from spotify
        self.assertNotIn(('MIA', 'M.I.A.'), matches)
        # C-oldplay is a title and therefore not in matches list even though it
        # resembles Coldplay
        self.assertNotIn(('C-oldplay', 'Coldplay'), matches)
        # The Whitelisted is not blacklisted, and can be whatever role he wants
        self.assertNotIn(('The Whitelisted', 'The Whitelisted'), matches)

        matches2 = find_offending_words(self.release2)
        # Ed Sheeran and Lynyrd Skynyrd is Remixer and Producer and should be in matches2-list
        self.assertIn(('Ed Sheeran', 'Ed Sheeran'), matches2)
        self.assertIn(('Lynyrd Skynyrd', 'Lynyrd Skynyrd'), matches2)
        # Sam Smith is ROLE_WRITER of the cover/remix and therefore not in matches2-list even
        # though it's a blacklisted name from spotify.
        self.assertNotIn(('Sam Smith', 'Sam Smith'), matches2)

    def test_find_blacklisted_artist_by_artist_names(self):
        """
        Tests that find_offending_artists() returns all the blacklisted artists
        based on a set of artists.
        """
        artist_names = [
            self.artist1,
            self.artist2,
            self.artist3,
            self.artist4,
            self.artist5,
        ]
        matches = find_offending_artists(artist_names)
        self.assertIn(('Ed Sheeran', 'Ed Sheeran'), matches)
        self.assertIn(('Lynyrd Skynyrd', 'Lynyrd Skynyrd'), matches)
        self.assertIn(('Sam Smith', 'Sam Smith'), matches)
        # Ed Sheeran & Lynyrd Skynyrd are blacklisted names, and should be in matches-list
        self.assertNotIn(('C-oldplay', 'Coldplay'), matches)
        self.assertNotIn(('MasterWriter', 'MasterWriter'), matches)
        self.assertNotIn(('The Whitelisted', 'The Whitelisted'), matches)
        # C-oldplay is a title and therefore not in matches list even though it resembles Coldplay
        # MasterWriter is not a black
