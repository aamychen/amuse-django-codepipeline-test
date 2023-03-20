import datetime
import random
from decimal import Decimal
from os.path import join

import factory.fuzzy
from django.conf import settings

from amuse.tasks import _calculate_django_file_checksum
from releases.models import SongArtistRole, ReleaseArtistRole, MetadataLanguage, Release
from users.tests.factories import UserFactory, Artistv2Factory
from .. import models
from ..models.release_store_delivery_status import ReleaseStoreDeliveryStatus


def generate_releases(num_records, release_status=None):
    '''
    Convenient function to populate a local database for development environment only.
    Creates as many releases as num_records with everything that is needed including
    creating users, artists, covert art, songs and song music file. Releases created
    has random statuses to simulate a production environment.
    '''
    releases = []
    for i in range(num_records):
        # Creates Release and User
        status = (
            random.choice(Release.STATUS_CHOICES)[0]
            if release_status is None
            else release_status
        )
        release = ReleaseFactory(status=status)
        releases.append(release)

        # Creates Artist and adds ReleaseArtist role
        artist = Artistv2Factory(owner=release.user, name=release.user.artist_name)
        ReleaseArtistRoleFactory(release=release, artist=artist, artist_sequence=1)

        # Creates CoverArt and checksum
        file_path = join(settings.BASE_DIR, 'releases/tests/cover.jpg')
        cover_art = CoverArtFactory(
            release=release,
            user_id=release.user.id,
            file__from_path=file_path,
            file__filename='random.jpg',
        )
        cover_art.checksum = _calculate_django_file_checksum(cover_art.file)
        cover_art.save()

        # Creates Song, SongFile and SongArtistRole
        song = SongFactory(release=release, filename='sample.flac')
        SongArtistRoleFactory(artist=artist, song=song, artist_sequence=1)
        SongFileFactory(song=song, type=models.SongFile.TYPE_FLAC, duration=1)
    return releases


class GenreFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Genre
        django_get_or_create = ('name',)

    status = models.Genre.STATUS_ACTIVE
    name = factory.Sequence('Genre {0}'.format)
    apple_code = factory.fuzzy.FuzzyText(length=10)


class StoreFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Store
        django_get_or_create = ('name',)

    name = factory.Faker('word')
    logo = factory.Faker('url')
    org_id = factory.fuzzy.FuzzyText(length=10)
    order = factory.fuzzy.FuzzyInteger(0, 1000)
    active = True
    admin_active = True
    is_pro = False
    show_on_top = False
    multi_batch_support = True


class StoreCategoryFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.StoreCategory

    name = factory.Faker('word')
    order = factory.fuzzy.FuzzyInteger(0, 1000)


class ReleaseFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Release

    type = models.Release.TYPE_SINGLE
    name = factory.Faker('word')
    label = factory.Faker('word')

    # TODO: flags

    schedule_type = models.Release.SCHEDULE_TYPE_STATIC
    release_date = factory.fuzzy.FuzzyDate(datetime.date(1984, 1, 1))
    release_version = factory.Sequence('v1.{0}'.format)

    link = factory.Faker('url')
    completed = True
    approved = True

    delivery_status = models.Release.DELIVERY_STATUS_SUCCESS
    status = models.Release.STATUS_APPROVED

    genre = factory.SubFactory(GenreFactory)
    upc = factory.SubFactory('codes.tests.factories.UPCFactory')
    user = factory.SubFactory('users.tests.factories.UserFactory')

    @factory.post_generation
    def stores(self, create, stores, **kwargs):
        if not create:
            return
        if stores:
            # A list of groups were passed in, use them
            for store in stores:
                self.stores.add(store)

    @factory.post_generation
    def countries(self, create, countries, **kwargs):
        if not create:
            return
        if countries:
            # A list of groups were passed in, use them
            for store in countries:
                self.stores.add(store)


class SongFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Song

    sequence = factory.Sequence(int)
    name = factory.Faker('word')
    version = factory.Sequence('v1.{0}'.format)
    recording_year = 1984
    filename = factory.Faker('file_name')
    isrc = factory.SubFactory('codes.tests.factories.ISRCFactory')
    genre = factory.SubFactory(GenreFactory)
    release = factory.SubFactory(ReleaseFactory, genre=factory.SelfAttribute('..genre'))
    meta_language = factory.SubFactory(
        'releases.tests.factories.MetadataLanguageFactory'
    )
    meta_audio_locale = factory.SubFactory(
        'releases.tests.factories.MetadataLanguageFactory'
    )

    class Params:
        create_songfiles = factory.Trait(
            mp3_file=factory.RelatedFactory(
                'releases.tests.factories.SongFileFactory', factory_related_name='song'
            ),
            flac_file=factory.RelatedFactory(
                'releases.tests.factories.SongFileFactory',
                factory_related_name='song',
                type=models.SongFile.TYPE_FLAC,
            ),
        )


class SongFileFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SongFile

    type = models.SongFile.TYPE_MP3

    duration = factory.fuzzy.FuzzyInteger(60 * 2, 60 * 5)

    song = factory.SubFactory(SongFactory)
    file = factory.django.FileField(filename=factory.Faker('file_name'), data=b'abc')


class SongFileUploadFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SongFileUpload

    filename = factory.Faker('file_name')
    user = factory.SubFactory('users.tests.factories.UserFactory')
    status = models.SongFileUpload.STATUS_COMPLETED
    song = factory.SubFactory(SongFactory)


class NewSongFileUploadFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SongFileUpload

    filename = factory.Faker('file_name')
    user = factory.SubFactory('users.tests.factories.UserFactory')


class SongArtistRoleFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SongArtistRole

    artist = factory.SubFactory(Artistv2Factory)
    song = factory.SubFactory(SongFactory)
    role = SongArtistRole.ROLE_PRIMARY_ARTIST


class ReleaseArtistRoleFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.ReleaseArtistRole

    artist = factory.SubFactory(Artistv2Factory)
    release = factory.SubFactory(ReleaseFactory)
    role = ReleaseArtistRole.ROLE_PRIMARY_ARTIST
    main_primary_artist = True


class CoverArtFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.CoverArt

    release = factory.SubFactory(
        'releases.tests.factories.ReleaseFactory', user=factory.SelfAttribute('..user')
    )
    user = factory.SubFactory('users.tests.factories.UserFactory')
    file = factory.django.FileField(filename=factory.Faker('file_name'), data=b'abc')
    width = factory.fuzzy.FuzzyInteger(200, 2000)
    height = factory.fuzzy.FuzzyInteger(200, 2000)


class RoyaltySplitFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.RoyaltySplit

    song = factory.SubFactory(SongFactory)
    user = factory.SubFactory(UserFactory)
    rate = Decimal("1.0000")
    status = models.RoyaltySplit.STATUS_PENDING
    is_locked = False


class MetadataLanguageFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.MetadataLanguage
        django_get_or_create = ["iso_639_1"]

    fuga_code = factory.SelfAttribute("iso_639_1")
    iso_639_1 = factory.fuzzy.FuzzyChoice(["en", "sv", "bs", "fi"])
    is_title_language = True
    is_lyrics_language = True
    sort_order = MetadataLanguage.DEFAULT_SORT_ORDER


class AssetLabelFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.AssetLabel

    name = factory.Faker('word')


class CommentsFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Comments

    release = factory.SubFactory(ReleaseFactory)
    text = factory.Faker('text')


class FugaMetadataFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.FugaMetadata

    release = factory.SubFactory(ReleaseFactory)
    product_id = factory.fuzzy.FuzzyInteger(200, 2000)
    status = "PUBLISHED"
    delivery_instructions_metadata = None


class FugaStoreFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.FugaStores

    external_id = factory.fuzzy.FuzzyInteger(200, 2000)
    name = factory.Faker('word')
    is_iip_dds = factory.Faker('pybool')
    is_ssf_dds = factory.Faker('pybool')


class FugaDeliveryHistoryFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.FugaDeliveryHistory

    external_id = factory.fuzzy.FuzzyInteger(200, 2000)
    release = factory.SubFactory(ReleaseFactory)
    fuga_store = factory.SubFactory(FugaStoreFactory)
    product_id = factory.fuzzy.FuzzyInteger(200, 2000)
    dated_at = factory.fuzzy.FuzzyDate(datetime.date(2018, 10, 1))
    action = "INSERT"
    state = "DELIVERED"


class FugaArtistFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.FugaArtist

    external_id = factory.fuzzy.FuzzyInteger(200, 2000)
    name = factory.Faker('word')


class ReleaseStoreDeliveryStatusFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.ReleaseStoreDeliveryStatus

    delivered_at = factory.fuzzy.FuzzyDate(datetime.date(2023, 1, 1))
    status = ReleaseStoreDeliveryStatus.STATUS_DELIVERED
