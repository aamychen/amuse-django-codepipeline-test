import amuse
from amuse.tests.test_api.base import AmuseAPITestCase
from releases.models import Release, Song
from amuse.api.actions.release import enforce_release_version
from releases.tests.factories import ReleaseFactory, SongFactory


class TestRelease(AmuseAPITestCase):
    def test_enforce_release_version_single(self):
        single = ReleaseFactory(type=Release.TYPE_SINGLE)
        song1 = SongFactory(version='Remix', release=single)
        enforce_release_version(single)

        assert single.release_version == song1.version

    def test_enforce_release_version_album_success(self):
        same_version_album = ReleaseFactory(type=Release.TYPE_ALBUM)
        song1 = SongFactory(version='Remix', release=same_version_album)
        song2 = SongFactory(version='Remix', release=same_version_album)
        enforce_release_version(same_version_album)

        assert (
            same_version_album.release_version
            == Release.RELEASE_VERSIONS[song1.version]
        )

    def test_enforce_release_version_album_fail(self):
        different_version_album = ReleaseFactory(
            type=Release.TYPE_ALBUM, release_version='v1.0'
        )
        song1 = SongFactory(version='Remix', release=different_version_album)
        song2 = SongFactory(version='Live', release=different_version_album)
        enforce_release_version(different_version_album)

        # Release version should default value
        assert different_version_album.release_version == 'v1.0'
