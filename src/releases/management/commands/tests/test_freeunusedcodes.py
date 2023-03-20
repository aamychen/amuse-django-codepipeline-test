import responses
from unittest import mock
from io import StringIO
from codes.models import Code, ISRC, UPC
from django.core.management import call_command
from django.test import TestCase
from releases.models import Release
from releases.tests.factories import ReleaseFactory, SongFactory


class FreeCodesTestCase(TestCase):
    @responses.activate
    def test_fake_codes_created(self):
        upc = UPC.objects.filter(code='0000000000000').first()
        self.assertIsNone(upc)

        isrc = ISRC.objects.filter(code='NULL00000000').first()
        self.assertIsNone(isrc)

        out = StringIO()
        call_command('freeunusedcodes', stdout=out)

        upc = UPC.objects.filter(code='0000000000000').first()
        self.assertIsNotNone(upc)
        self.assertIs(upc.status, Code.STATUS_USED)

        isrc = ISRC.objects.filter(code='NULL00000000').first()
        self.assertIsNotNone(isrc)
        self.assertIs(isrc.status, Code.STATUS_USED)

    @responses.activate
    def test_not_deleted_release_is_untouched(self):
        release = ReleaseFactory(status=Release.STATUS_PENDING)
        initial_upc = release.upc

        initial_isrcs = [SongFactory(release=release).isrc for index in range(0, 5)]

        out = StringIO()
        call_command('freeunusedcodes', '--commit', '--limit=1000', stdout=out)

        fake_upc = UPC.objects.get(code='0000000000000')
        fake_isrc = ISRC.objects.get(code='NULL00000000')

        release.refresh_from_db()
        self.assertNotEqual(release.upc, fake_upc)
        self.assertEqual(release.upc, initial_upc)
        self.assertEqual(release.songs.count(), 5)
        for index, song in enumerate(release.songs.all()):
            self.assertNotEqual(song.isrc, fake_isrc)
            self.assertEqual(song.isrc, initial_isrcs[index])

    @responses.activate
    def test_delivered_but_deleted_release_keeps_codes(self):
        release = ReleaseFactory(status=Release.STATUS_PENDING)
        initial_upc = release.upc

        initial_isrcs = [SongFactory(release=release).isrc for index in range(0, 5)]

        release.status = Release.STATUS_SUBMITTED
        release.save()
        release.status = Release.STATUS_DELIVERED
        release.save()
        release.status = Release.STATUS_DELETED
        release.save()

        out = StringIO()
        call_command('freeunusedcodes', '--commit', '--limit=1000', stdout=out)

        fake_upc = UPC.objects.get(code='0000000000000')
        fake_isrc = ISRC.objects.get(code='NULL00000000')

        release.refresh_from_db()
        self.assertNotEqual(release.upc, fake_upc)
        self.assertEqual(release.upc, initial_upc)
        self.assertEqual(release.songs.count(), 5)
        for index, song in enumerate(release.songs.all()):
            self.assertNotEqual(song.isrc, fake_isrc)
            self.assertEqual(song.isrc, initial_isrcs[index])

    @responses.activate
    def test_never_delivered_deleted_release_have_codes_removed(self):
        release = ReleaseFactory(status=Release.STATUS_PENDING)
        initial_upc = release.upc

        initial_isrcs = [SongFactory(release=release).isrc for index in range(0, 5)]

        release.status = Release.STATUS_SUBMITTED
        release.save()
        release.status = Release.STATUS_DELETED
        release.save()

        out = StringIO()
        call_command('freeunusedcodes', '--commit', '--limit=1000', stdout=out)

        fake_upc = UPC.objects.get(code='0000000000000')
        fake_isrc = ISRC.objects.get(code='NULL00000000')

        release.refresh_from_db()
        self.assertEqual(release.upc, fake_upc)
        self.assertEqual(release.songs.count(), 5)
        for index, song in enumerate(release.songs.all()):
            self.assertEqual(song.isrc, fake_isrc)

    @responses.activate
    def test_nothing_happens_with_commit_flag_false(self):
        release = ReleaseFactory(status=Release.STATUS_PENDING)
        initial_upc = release.upc

        initial_isrcs = [SongFactory(release=release).isrc for index in range(0, 5)]

        release.status = Release.STATUS_SUBMITTED
        release.save()
        release.status = Release.STATUS_DELETED
        release.save()

        out = StringIO()
        call_command('freeunusedcodes', '--limit=1000', stdout=out)

        fake_upc = UPC.objects.get(code='0000000000000')
        fake_isrc = ISRC.objects.get(code='NULL00000000')

        release.refresh_from_db()
        self.assertNotEqual(release.upc, fake_upc)
        self.assertEqual(release.upc, initial_upc)
        self.assertEqual(release.songs.count(), 5)
        for index, song in enumerate(release.songs.all()):
            self.assertNotEqual(song.isrc, fake_isrc)
            self.assertEqual(song.isrc, initial_isrcs[index])

    @responses.activate
    def test_limit_is_honored(self):
        releases = [
            ReleaseFactory(status=Release.STATUS_PENDING) for index in range(0, 7)
        ]

        # Make history
        for release in releases:
            release.status = Release.STATUS_DELETED
            release.save()

        limit = 2

        out = StringIO()
        call_command('freeunusedcodes', '--commit', f'--limit={limit}', stdout=out)

        fake_upc = UPC.objects.get(code='0000000000000')

        untouched_count = len(releases)
        for release in releases:
            release.refresh_from_db()
            if release.upc == fake_upc:
                untouched_count -= 1

        self.assertEqual(untouched_count, 5)

    @responses.activate
    def test_releases_with_uncertain_history_ignored(self):
        release = ReleaseFactory(status=Release.STATUS_DELETED)
        initial_upc = release.upc

        out = StringIO()
        call_command('freeunusedcodes', '--commit', '--limit=1000', stdout=out)

        release.refresh_from_db()
        self.assertEqual(release.upc, initial_upc)

    @responses.activate
    def test_codes_cleared_when_unused(self):
        release = ReleaseFactory(status=Release.STATUS_PENDING)
        initial_upc = release.upc

        initial_isrcs = [SongFactory(release=release).isrc for index in range(0, 2)]

        codes = [initial_upc] + initial_isrcs
        for code in codes:
            code.refresh_from_db()
            self.assertEqual(code.status, Code.STATUS_USED)

        release.status = Release.STATUS_SUBMITTED
        release.save()
        release.status = Release.STATUS_DELETED
        release.save()

        out = StringIO()
        call_command('freeunusedcodes', '--commit', '--limit=1000', stdout=out)

        for code in codes:
            code.refresh_from_db()
            self.assertEqual(code.status, Code.STATUS_UNUSED)

    @responses.activate
    def test_codes_not_cleared_when_still_used(self):
        deleted_release = ReleaseFactory(status=Release.STATUS_PENDING)
        initial_upc = deleted_release.upc

        initial_isrcs = [
            SongFactory(release=deleted_release).isrc for index in range(0, 2)
        ]

        codes = [initial_upc] + initial_isrcs
        for code in codes:
            code.refresh_from_db()
            self.assertEqual(code.status, Code.STATUS_USED)

        deleted_release.status = Release.STATUS_SUBMITTED
        deleted_release.save()
        deleted_release.status = Release.STATUS_DELETED
        deleted_release.save()

        non_deleted_release = ReleaseFactory(
            status=Release.STATUS_PENDING, upc=initial_upc
        )

        for isrc in initial_isrcs:
            SongFactory(release=non_deleted_release, isrc=isrc)

        out = StringIO()
        call_command('freeunusedcodes', '--commit', '--limit=1000', stdout=out)

        for code in codes:
            code.refresh_from_db()
            self.assertEqual(code.status, Code.STATUS_USED)
