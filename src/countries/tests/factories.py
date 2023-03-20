import factory.fuzzy
from .. import models


class CountryFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Country
        django_get_or_create = ('code',)

    code = factory.fuzzy.FuzzyText(length=2)
    name = factory.Faker('country')
    vat_percentage = factory.fuzzy.FuzzyDecimal(0, 1, precision=2)
    dial_code = factory.fuzzy.FuzzyInteger(1, 2000)
    is_yt_content_id_enabled = True


class CurrencyFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Currency
        django_get_or_create = ('code',)

    code = factory.fuzzy.FuzzyText(length=3)
    name = factory.Faker('country')
    decimals = factory.fuzzy.FuzzyInteger(0, 4)
