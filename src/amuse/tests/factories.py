import datetime

import factory
from factory.fuzzy import FuzzyChoice
import pytz

from amuse.models import (
    Image,
    SupportEvent,
    SupportRelease,
    Link,
    Transcoding,
    ACRCloudMatch,
)
from amuse.models.bulk_delivery_job import BulkDeliveryJob
from amuse.models.deliveries import Batch, BatchDelivery, BatchDeliveryRelease


class ImageFactory(factory.DjangoModelFactory):
    class Meta:
        model = Image

    path = factory.Faker('file_path')


class BatchFactory(factory.DjangoModelFactory):
    class Meta:
        model = Batch

    file = factory.django.FileField()


class BatchDeliveryFactory(factory.DjangoModelFactory):
    class Meta:
        model = BatchDelivery


class BatchDeliveryReleaseFactory(factory.DjangoModelFactory):
    class Meta:
        model = BatchDeliveryRelease

    delivery = factory.SubFactory(BatchDeliveryFactory)
    release = factory.SubFactory('releases.tests.factories.ReleaseFactory')


class TranscodingFactory(factory.DjangoModelFactory):
    class Meta:
        model = Transcoding

    transcoder_job = factory.fuzzy.FuzzyText(length=32)
    transcoder_name = Transcoding.ELASTIC_TRANSCODER
    song = factory.SubFactory("releases.tests.factories.SongFactory")


class SupportReleaseFactory(factory.DjangoModelFactory):
    class Meta:
        model = SupportRelease

    assignee = factory.SubFactory('users.tests.factories.UserFactory')
    release = factory.SubFactory('releases.tests.factories.ReleaseFactory')
    prepared = False


class SupportEventFactory(factory.DjangoModelFactory):
    class Meta:
        model = SupportEvent

    event = SupportEvent.ASSIGNED
    release = factory.SubFactory('releases.tests.factories.ReleaseFactory')
    user = factory.SubFactory('users.tests.factories.UserFactory')


class LinkFactory(factory.DjangoModelFactory):
    class Meta:
        model = Link


class BulkDeliveryJobFactory(factory.DjangoModelFactory):
    class Meta:
        model = BulkDeliveryJob

    type = BulkDeliveryJob.JOB_TYPE_INSERT
    input_file = factory.django.FileField(
        filename="{}.csv".format(factory.Faker('file_name')), data=b'abc'
    )


class ACRCloudMatchFactory(factory.DjangoModelFactory):
    class Meta:
        model = ACRCloudMatch

    score = factory.fuzzy.FuzzyInteger(0, 90)
    offset = factory.fuzzy.FuzzyInteger(0, 5)
    song = factory.SubFactory("releases.tests.factories.SongFactory")
    track_title = factory.Faker('word')
    artist_name = factory.Faker('word')
    match_isrc = factory.SubFactory('codes.tests.factories.ISRCFactory')
