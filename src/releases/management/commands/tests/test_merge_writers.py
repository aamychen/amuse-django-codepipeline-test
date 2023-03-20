import responses
from django.test import override_settings
from django.core.management import call_command
from django.test import TestCase
from collections import OrderedDict
from amuse.tests.helpers import (
    add_zendesk_mock_post_response,
    ZENDESK_MOCK_API_URL_TOKEN,
)

from releases.models import SongArtistRole
from releases.tests.factories import (
    SongFactory,
    ReleaseFactory,
    SongArtistRoleFactory,
    UserFactory,
    Artistv2Factory,
)

from releases.management.commands.merge_writers import (
    find_unmergeable_artists,
    update_unmergeables,
)

ROLE_PRIMARY_ARTIST = SongArtistRole.ROLE_PRIMARY_ARTIST
ROLE_FEATURED_ARTIST = SongArtistRole.ROLE_FEATURED_ARTIST
ROLE_WRITER = SongArtistRole.ROLE_WRITER
ROLE_PRODUCER = SongArtistRole.ROLE_PRODUCER
ROLE_MIXER = SongArtistRole.ROLE_MIXER
ROLE_REMIXER = SongArtistRole.ROLE_REMIXER


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class MergeWritersTestCase(TestCase):
    @responses.activate
    def test_merge_2_writers_on_different_songs(self):
        add_zendesk_mock_post_response()

        u1 = UserFactory()
        r1 = ReleaseFactory(user=u1)

        s1 = SongFactory(release=r1)
        s2 = SongFactory(release=r1)

        a1 = Artistv2Factory(name='Kurajber')
        a2 = Artistv2Factory(name='Kurajber')

        SongArtistRoleFactory(song=s1, artist=a1, role=ROLE_WRITER)
        SongArtistRoleFactory(song=s2, artist=a2, role=ROLE_WRITER)

        call_command('merge_writers')

        actual = list(SongArtistRole.objects.all())

        self.assertEqual(2, len(actual))
        self.assertEqual(a1, actual[0].artist)
        self.assertEqual(a1, actual[1].artist)

    @responses.activate
    def test_merge_2_pair_of_writers_on_different_songs(self):
        add_zendesk_mock_post_response()

        u1 = UserFactory()
        r1 = ReleaseFactory(user=u1)

        s1 = SongFactory(release=r1)
        s2 = SongFactory(release=r1)

        a1 = Artistv2Factory(name='Kurajber')
        a2 = Artistv2Factory(name='Kurajber')
        a3 = Artistv2Factory(name='John')
        a4 = Artistv2Factory(name='John')

        SongArtistRoleFactory(song=s1, artist=a1, role=ROLE_WRITER)
        SongArtistRoleFactory(song=s2, artist=a2, role=ROLE_WRITER)
        SongArtistRoleFactory(song=s1, artist=a3, role=ROLE_WRITER)
        SongArtistRoleFactory(song=s2, artist=a4, role=ROLE_WRITER)

        call_command('merge_writers')

        actual = list(SongArtistRole.objects.all())

        self.assertEqual(4, len(actual))
        self.assertEqual(a1, actual[0].artist)
        self.assertEqual(a1, actual[1].artist)
        self.assertEqual(a3, actual[2].artist)
        self.assertEqual(a3, actual[3].artist)

    @responses.activate
    def test_do_not_merge_2_artists_with_same_name_on_single_song(self):
        add_zendesk_mock_post_response()

        u1 = UserFactory()
        r1 = ReleaseFactory(user=u1)

        s1 = SongFactory(release=r1)
        s2 = SongFactory(release=r1)

        a1 = Artistv2Factory(name='Kurajber')
        a2 = Artistv2Factory(name='Kurajber')

        SongArtistRoleFactory(song=s1, artist=a1, role=ROLE_WRITER)
        SongArtistRoleFactory(song=s1, artist=a2, role=ROLE_WRITER)
        SongArtistRoleFactory(song=s2, artist=a2, role=ROLE_WRITER)

        call_command('merge_writers')

        actual = list(SongArtistRole.objects.all())
        actual.sort(key=lambda x: x.id)

        # nothing changed (there are two artists with a same name on the same song)
        self.assertEqual(3, len(actual))
        self.assertEqual(a1, actual[0].artist)
        self.assertEqual(s1, actual[0].song)

        self.assertEqual(a2, actual[1].artist)
        self.assertEqual(s1, actual[1].song)

        self.assertEqual(a2, actual[2].artist)
        self.assertEqual(s2, actual[2].song)

    @responses.activate
    def test_complex_scenario(self):
        add_zendesk_mock_post_response()

        u1 = UserFactory()
        r1 = ReleaseFactory(user=u1)

        s1 = SongFactory(release=r1)
        s2 = SongFactory(release=r1)

        a1 = Artistv2Factory(name='Kurajber')
        a2 = Artistv2Factory(name='Kurajber')
        a3 = Artistv2Factory(name='Kurajber')
        a4 = Artistv2Factory(name='Kurajber')

        SongArtistRoleFactory(song=s1, artist=a1, role=ROLE_WRITER)
        SongArtistRoleFactory(song=s2, artist=a2, role=ROLE_WRITER)
        SongArtistRoleFactory(song=s2, artist=a3, role=ROLE_WRITER)
        SongArtistRoleFactory(song=s2, artist=a4, role=ROLE_WRITER)

        call_command('merge_writers')

        actual = list(SongArtistRole.objects.all())
        actual.sort(key=lambda x: x.id)

        self.assertEqual(4, len(actual))
        self.assertEqual(a1, actual[0].artist)
        self.assertEqual(a1, actual[1].artist)
        self.assertEqual(a3, actual[2].artist)
        self.assertEqual(a4, actual[3].artist)


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class FindUnmergeableArtistsTestCase(TestCase):
    @responses.activate
    def test_all_artists_are_unmergable(self):
        add_zendesk_mock_post_response()

        u1 = UserFactory(artist_name='kurajber')

        a1 = Artistv2Factory(name='kurajber')
        a2 = Artistv2Factory(name='Kurajber')
        a3 = Artistv2Factory(name='kurajber')

        r1 = ReleaseFactory(name='REL-A', user=u1)

        s1 = SongFactory(release=r1, name='Song-A')

        writer_roles = [
            SongArtistRoleFactory(song=s1, artist=a1, role=ROLE_WRITER),
            SongArtistRoleFactory(song=s1, artist=a2, role=ROLE_WRITER),
            SongArtistRoleFactory(song=s1, artist=a3, role=ROLE_WRITER),
        ]

        expected = OrderedDict()
        expected[a1.id] = {a2.id, a3.id}
        expected[a2.id] = {a1.id, a3.id}
        expected[a3.id] = {a1.id, a2.id}

        actual = find_unmergeable_artists(writer_roles)
        for artist_id, unmergeables in expected.items():
            self.assertTrue(actual.get(artist_id))
            self.assertSetEqual(unmergeables, actual[artist_id])

    @responses.activate
    def test_no_unmergables(self):
        add_zendesk_mock_post_response()

        u1 = UserFactory(artist_name='kurajber')

        a1 = Artistv2Factory(name='kurajber')
        a2 = Artistv2Factory(name='Kurajber')
        a3 = Artistv2Factory(name='kurajber')

        r1 = ReleaseFactory(name='REL-A', user=u1)

        s1 = SongFactory(release=r1, name='Song-A')
        s2 = SongFactory(release=r1, name='Song-B')
        s3 = SongFactory(release=r1, name='Song-B')

        writer_roles = [
            SongArtistRoleFactory(song=s1, artist=a1, role=ROLE_WRITER),
            SongArtistRoleFactory(song=s2, artist=a2, role=ROLE_WRITER),
            SongArtistRoleFactory(song=s3, artist=a3, role=ROLE_WRITER),
        ]

        actual = find_unmergeable_artists(writer_roles)
        self.assertEqual(3, len(actual))
        for key, value in actual.items():
            # empty sets
            self.assertEqual(0, len(value))

    @responses.activate
    def test_some_items_are_unmergables(self):
        add_zendesk_mock_post_response()

        u1 = UserFactory(artist_name='kurajber')

        a1 = Artistv2Factory(name='kurajber')
        a2 = Artistv2Factory(name='Kurajber')
        a3 = Artistv2Factory(name='kurajber')
        a4 = Artistv2Factory(name='kurajber')

        r1 = ReleaseFactory(name='REL-A', user=u1)

        s1 = SongFactory(release=r1, name='Song-A')
        s2 = SongFactory(release=r1, name='Song-B')
        s3 = SongFactory(release=r1, name='Song-B')

        writer_roles = [
            SongArtistRoleFactory(song=s1, artist=a1, role=ROLE_WRITER),
            SongArtistRoleFactory(song=s2, artist=a2, role=ROLE_WRITER),
            SongArtistRoleFactory(song=s3, artist=a3, role=ROLE_WRITER),
            SongArtistRoleFactory(song=s1, artist=a4, role=ROLE_WRITER),
        ]

        expected = OrderedDict()
        expected[a1.id] = {a4.id}
        expected[a2.id] = set()
        expected[a3.id] = set()
        expected[a4.id] = {a1.id}

        actual = find_unmergeable_artists(writer_roles)
        self.assertEqual(4, len(actual))
        for artist_id, unmergables in expected.items():
            self.assertTrue(actual.get(artist_id) is not None)
            self.assertSetEqual(unmergables, actual[artist_id])


@override_settings(**ZENDESK_MOCK_API_URL_TOKEN)
class UpdateUnmergeableArtistsTestCase(TestCase):
    def test_update_unmergeables(self):
        unmergeables = OrderedDict()
        unmergeables[1] = {2, 3, 4}
        unmergeables[2] = {1, 3, 4}
        unmergeables[3] = {1, 2, 4}
        unmergeables[4] = {1, 2, 3}
        unmergeables[5] = {6}
        unmergeables[6] = {5}

        update_unmergeables(unmergeables, 20, 3)

        self.assertSetEqual({2, 3, 4, 20}, unmergeables[1])
        self.assertSetEqual({1, 3, 4, 20}, unmergeables[2])
        self.assertSetEqual({1, 2, 4}, unmergeables[3])
        self.assertSetEqual({1, 2, 3, 20}, unmergeables[4])
        self.assertSetEqual({6}, unmergeables[5])
        self.assertSetEqual({5}, unmergeables[6])
        self.assertSetEqual({1, 2, 4}, unmergeables[20])
