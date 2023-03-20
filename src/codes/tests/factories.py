import factory.fuzzy

from releases.models import MetadataLanguage
from .. import models


class UPCFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.UPC
        django_get_or_create = ("code",)

    code = factory.fuzzy.FuzzyText(length=12)
    status = models.Code.STATUS_USED


class ISRCFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.ISRC
        django_get_or_create = ("code",)

    code = factory.Sequence('TEST{0:08}'.format)
    status = models.Code.STATUS_USED


class MetadataLanguageFactory(factory.DjangoModelFactory):
    class Meta:
        model = MetadataLanguage

    name = factory.fuzzy.FuzzyText(length=10)
    fuga_code = factory.fuzzy.FuzzyText(length=2)
    iso_639_1 = factory.LazyAttribute(lambda instance: instance.fuga_code)
