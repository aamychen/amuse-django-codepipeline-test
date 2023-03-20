import pathlib
import csv
from unittest import mock

import pytest
from django.core.files.base import ContentFile

from amuse.models.bulk_delivery_job import BulkDeliveryJob
from amuse.models.bulk_delivery_job_results import BulkDeliveryJobResult
from amuse.services.delivery.checks import get_store_delivery_checks
from amuse.tests.factories import (
    BulkDeliveryJobFactory,
)
from codes.models import ISRC
from codes.tests.factories import ISRCFactory
from releases.models import Release, Song, Store
from releases.tests.factories import (
    StoreFactory,
    ReleaseFactory,
    generate_releases,
    ReleaseArtistRoleFactory,
    SongFactory,
)
from users.tests.factories import Artistv2Factory

absolute_src_path = pathlib.Path(__file__).parent.resolve()


def load_fixture(filename):
    return ContentFile(
        content=open(f"{absolute_src_path}/fixtures/{filename}").read().encode('utf-8'),
        name="simple.csv",
    )


@pytest.mark.django_db
def test_get_release_ids_simple_case():
    store = StoreFactory(internal_name='unlimited_dsp')
    job = BulkDeliveryJob(
        input_file=load_fixture("simple.csv"), type=BulkDeliveryJob.JOB_TYPE_INSERT
    )
    job.store = store
    job.save()
    songs, releases = job.get_release_and_song_ids()

    assert releases == [
        6072,
        10051,
        14992,
        38179,
        45050,
        67744,
        93093,
        101732,
        117096,
    ]


@pytest.mark.django_db
def test_get_release_ids_removes_duplicates_and_invalids():
    store = StoreFactory(internal_name='unlimited_dsp')
    job = BulkDeliveryJob(
        input_file=load_fixture("contains_invalid_release_ids.csv"),
        type=BulkDeliveryJob.JOB_TYPE_INSERT,
    )
    job.store = store
    job.save()
    songs, releases = job.get_release_and_song_ids()

    assert releases == [
        6072,
        10051,
        14992,
        38179,
        45050,
        67744,
        93093,
        101732,
        117096,
    ]


@pytest.mark.django_db
def test_get_release_ids_for_artist():
    store = StoreFactory(internal_name='unlimited_dsp')

    artist_1 = Artistv2Factory()
    artist_2 = Artistv2Factory()
    release_1 = ReleaseFactory()
    release_2 = ReleaseFactory()
    release_3 = ReleaseFactory()

    ReleaseArtistRoleFactory(artist=artist_1, release=release_1)
    ReleaseArtistRoleFactory(artist=artist_1, release=release_2)
    ReleaseArtistRoleFactory(artist=artist_2, release=release_3)

    file_name = "temp_artist_id.csv"
    with open(file_name, 'w') as csv_file:
        wr = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
        wr.writerow(["artist_id"])
        wr.writerow([artist_1.id])
        wr.writerow([artist_2.id])

    job = BulkDeliveryJob(
        input_file=ContentFile(
            content=open(file_name).read().encode('utf-8'), name="simple.csv"
        ),
        type=BulkDeliveryJob.JOB_TYPE_INSERT,
    )

    job.store = store
    job.save()
    songs, releases = job.get_release_and_song_ids()

    assert releases == [release_1.id, release_2.id, release_3.id]


@pytest.mark.django_db
def test_execute_with_empty_file():
    spotify = StoreFactory(name="Spotify", internal_name="spotify")
    job = BulkDeliveryJobFactory(
        type=BulkDeliveryJob.JOB_TYPE_INSERT,
        mode=BulkDeliveryJob.MODE_OVERRIDE_RELEASE_STORES,
    )
    job.store = spotify
    job.execute()

    job.refresh_from_db()
    assert job.status == BulkDeliveryJob.STATUS_FAILED
    assert job.description in 'No valid release_ids found'
    assert BulkDeliveryJobResult.objects.filter(job=job).count() == 0


@pytest.mark.django_db
def test_execute_with_unsupported_mode():
    # TODO: Temporary test to be removed when 'Only fuga release stores' mode is supported
    spotify = StoreFactory(name="Spotify", internal_name="spotify")
    job = BulkDeliveryJobFactory(
        input_file=load_fixture("simple.csv"),
        type=BulkDeliveryJob.JOB_TYPE_INSERT,
        mode=BulkDeliveryJob.MODE_ONLY_FUGA_RELEASE_STORES,
    )
    job.store = spotify
    job.execute()

    job.refresh_from_db()
    assert job.status == BulkDeliveryJob.STATUS_FAILED
    assert job.description == 'Cannot process this mode at this point in time'
    assert BulkDeliveryJobResult.objects.filter(job=job).count() == 0


@pytest.mark.django_db
def test_execute_with_prevented_releases():
    spotify = StoreFactory(name="Spotify", internal_name="spotify", org_id=10)
    job = BulkDeliveryJobFactory(type=BulkDeliveryJob.JOB_TYPE_INSERT)
    job.store = spotify

    num_releases = 1
    releases = generate_releases(num_releases, Release.STATUS_REJECTED)

    release_ids = sorted([release.id for release in releases])

    def get_release_and_song_ids(_):
        return [], release_ids

    with mock.patch(
        'amuse.models.bulk_delivery_job.BulkDeliveryJob.get_release_and_song_ids',
        get_release_and_song_ids,
    ) as mock_release_ids_from_file:
        job.execute()

    description = 'Release status is not in Approved, Delivered or Released state'
    results = BulkDeliveryJobResult.objects.filter(
        job_id=job.id,
        status=BulkDeliveryJobResult.STATUS_PREVENTED,
        description=description,
        store=None,
    )
    assert results.count() == len(releases)

    job.refresh_from_db()
    assert job.status == BulkDeliveryJob.STATUS_COMPLETED
    assert job.description == 'Job completed'


@pytest.mark.django_db
def test_execute_with_pro_store_and_free_user():
    spotify = StoreFactory(
        name="Spotify", internal_name="spotify", is_pro=True, org_id=10
    )
    job = BulkDeliveryJobFactory(type=BulkDeliveryJob.JOB_TYPE_INSERT)
    job.store = spotify

    num_releases = 1
    releases = generate_releases(num_releases, Release.STATUS_APPROVED)

    release_ids = sorted([release.id for release in releases])

    def get_release_and_song_ids(_):
        return [], release_ids

    with mock.patch(
        'amuse.models.bulk_delivery_job.BulkDeliveryJob.get_release_and_song_ids',
        get_release_and_song_ids,
    ) as mock_release_ids_from_file:
        job.execute()

    description = (
        'Operation denied due to release owner not having a Pro or Plus account'
    )
    results = BulkDeliveryJobResult.objects.filter(
        job_id=job.id,
        status=BulkDeliveryJobResult.STATUS_PREVENTED,
        description=description,
        store=spotify,
    )
    assert results.count() == len(releases)

    job.refresh_from_db()
    assert job.status == BulkDeliveryJob.STATUS_COMPLETED
    assert job.description == 'Job completed'


@pytest.mark.django_db
def test_execute_with_explicit_release_track_to_tencent():
    tencent = StoreFactory(name="Tencent", internal_name="tencent", org_id=11)
    job = BulkDeliveryJobFactory(type=BulkDeliveryJob.JOB_TYPE_INSERT)
    job.store = tencent

    num_releases = 1
    releases = generate_releases(num_releases, Release.STATUS_APPROVED)
    for song in releases[0].songs.all():
        song.explicit = Song.EXPLICIT_TRUE
        song.save()

    release_ids = sorted([release.id for release in releases])

    def get_release_and_song_ids(_):
        return [], release_ids

    with mock.patch(
        'amuse.models.bulk_delivery_job.BulkDeliveryJob.get_release_and_song_ids',
        get_release_and_song_ids,
    ) as mock_release_ids_from_file:
        job.execute()

    description = 'Prevented because the release contains an explicit track'
    results = BulkDeliveryJobResult.objects.filter(
        job_id=job.id,
        status=BulkDeliveryJobResult.STATUS_PREVENTED,
        description=description,
        store=tencent,
    )
    assert results.count() == len(releases)

    job.refresh_from_db()
    assert job.status == BulkDeliveryJob.STATUS_COMPLETED
    assert job.description == 'Job completed'


@pytest.mark.django_db
def test_get_checks_after_override():
    youtube_cid = StoreFactory(
        name="Youtube CID", internal_name="youtube_content_id", org_id=11
    )
    job = BulkDeliveryJobFactory(
        type=BulkDeliveryJob.JOB_TYPE_INSERT,
        checks_to_override=['ProStoreCheck', 'FugaCheck'],
    )
    job.store = youtube_cid

    num_releases = 1
    release = generate_releases(num_releases, Release.STATUS_APPROVED)[0]

    checks = [
        check(
            release=release,
            store=Store.from_internal_name('youtube_content_id'),
            operation='takedown',
        )
        for check in get_store_delivery_checks('youtube_content_id')
    ]
    num_checks_before_check_overrides = len(checks)
    checks = job.get_checks_after_override(checks)
    num_checks_after_check_overrides = len(checks)
    assert num_checks_before_check_overrides == num_checks_after_check_overrides + 2


@pytest.mark.django_db
def test_get_release_and_song_ids_with_isrcs():
    store = StoreFactory(internal_name='youtube_content_id')

    release_1 = ReleaseFactory()
    isrc_1 = ISRCFactory(status=ISRC.STATUS_USED)
    isrc_2 = ISRCFactory(status=ISRC.STATUS_UNUSED)
    song_1 = SongFactory(isrc=isrc_1, release=release_1)

    file_name = "temp_artist_id.csv"
    with open(file_name, 'w') as csv_file:
        wr = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL)
        wr.writerow(["isrc"])
        wr.writerow([isrc_1.code])
        wr.writerow([isrc_2.code])

    job = BulkDeliveryJob(
        input_file=ContentFile(
            content=open(file_name).read().encode('utf-8'), name="simple.csv"
        ),
        type=BulkDeliveryJob.JOB_TYPE_INSERT,
    )

    job.store = store
    job.save()
    songs, releases = job.get_release_and_song_ids()

    assert songs == [song_1.id]
    assert releases == [release_1.id]


@pytest.mark.django_db
def test_execute_youtube_CID_change_for_isrc():
    store = StoreFactory(name='youtube_content_id', internal_name='youtube_content_id')
    release_1 = ReleaseFactory(status=Release.STATUS_APPROVED)
    release_1.stores.add(store)
    isrc_1 = ISRCFactory(status=ISRC.STATUS_USED)
    song_1 = SongFactory(
        isrc=isrc_1, release=release_1, youtube_content_id=Song.YT_CONTENT_ID_NONE
    )

    job = BulkDeliveryJobFactory(type=BulkDeliveryJob.JOB_TYPE_UPDATE)
    job.store = store
    job.youtube_content_id = Song.YT_CONTENT_ID_MONETIZE

    def get_release_and_song_ids(_):
        return [song_1.id], [release_1.id]

    with mock.patch(
        'amuse.models.bulk_delivery_job.BulkDeliveryJob.get_release_and_song_ids',
        get_release_and_song_ids,
    ) as mock_release_ids_from_file:
        job.execute()

    job.refresh_from_db()
    song_1.refresh_from_db()
    assert job.status == BulkDeliveryJob.STATUS_COMPLETED
    assert BulkDeliveryJobResult.objects.filter(job=job).count() == 1
    assert song_1.youtube_content_id == Song.YT_CONTENT_ID_MONETIZE


@pytest.mark.django_db
def test_execute_youtube_CID_update_without_select_youtube_CID_store():
    release_1 = ReleaseFactory(status=Release.STATUS_APPROVED)
    isrc_1 = ISRCFactory(status=ISRC.STATUS_USED)
    song_1 = SongFactory(
        isrc=isrc_1, release=release_1, youtube_content_id=Song.YT_CONTENT_ID_NONE
    )
    description = 'The store has to be set to \'Youtube Content ID\' when you\'ve chosen an option for Youtube content id update.'

    job = BulkDeliveryJobFactory(type=BulkDeliveryJob.JOB_TYPE_UPDATE)
    job.store = None
    job.youtube_content_id = Song.YT_CONTENT_ID_MONETIZE

    def get_release_and_song_ids(_):
        return [song_1.id], [release_1.id]

    with mock.patch(
        'amuse.models.bulk_delivery_job.BulkDeliveryJob.get_release_and_song_ids',
        get_release_and_song_ids,
    ) as mock_release_ids_from_file:
        job.execute()

    job.refresh_from_db()
    song_1.refresh_from_db()
    assert job.status == BulkDeliveryJob.STATUS_FAILED
    assert job.description == description
    assert BulkDeliveryJobResult.objects.filter(job=job).count() == 0
    assert song_1.youtube_content_id == Song.YT_CONTENT_ID_NONE


@pytest.mark.django_db
def test_execute_youtube_CID_change_without_select_CID_option():
    store = StoreFactory(name='youtube_content_id', internal_name='youtube_content_id')
    release_1 = ReleaseFactory(status=Release.STATUS_APPROVED)
    release_1.stores.add(store)
    isrc_1 = ISRCFactory(status=ISRC.STATUS_USED)
    song_1 = SongFactory(
        isrc=isrc_1, release=release_1, youtube_content_id=Song.YT_CONTENT_ID_NONE
    )
    description = 'When you set the store to \'Youtube Content ID\', you should also select an option in order to update Youtube content id. '

    job = BulkDeliveryJobFactory(type=BulkDeliveryJob.JOB_TYPE_UPDATE)
    job.store = store
    job.youtube_content_id = None

    def get_release_and_song_ids(_):
        return [song_1.id], [release_1.id]

    with mock.patch(
        'amuse.models.bulk_delivery_job.BulkDeliveryJob.get_release_and_song_ids',
        get_release_and_song_ids,
    ) as mock_release_ids_from_file:
        job.execute()

    job.refresh_from_db()
    song_1.refresh_from_db()
    assert job.status == BulkDeliveryJob.STATUS_FAILED
    assert job.description == description
    assert BulkDeliveryJobResult.objects.filter(job=job).count() == 0
    assert song_1.youtube_content_id == Song.YT_CONTENT_ID_NONE
