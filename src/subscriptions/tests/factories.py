import factory

from countries.tests.factories import CurrencyFactory, CountryFactory
from subscriptions.models import (
    Subscription,
    SubscriptionPlan,
    PriceCard,
    IntroductoryPriceCard,
)
from users.tests.factories import UserFactory


class SubscriptionPlanFactory(factory.DjangoModelFactory):
    name = factory.Faker("name")
    period = factory.fuzzy.FuzzyInteger(1, 120)
    trial_days = factory.fuzzy.FuzzyInteger(1, 90)
    apple_product_id = factory.Faker("name")
    google_product_id = factory.Faker("name")
    is_public = True
    tier = SubscriptionPlan.TIER_PRO

    class Meta:
        model = SubscriptionPlan

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        manager = cls._get_manager(model_class)
        create_card = kwargs.pop('create_card', True)
        price = kwargs.pop('price', factory.fuzzy.FuzzyDecimal(1, 1000, precision=2))
        currency = kwargs.pop('currency', factory.SubFactory(CurrencyFactory))
        plan = manager.create(*args, **kwargs)
        if create_card:
            card = PriceCardFactory(plan=plan, price=price, currency=currency)
        return plan

    @factory.post_generation
    def countries(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for country in extracted:
                for card in self.pricecard_set.all():
                    card.countries.add(country)
        else:
            country = CountryFactory(code='US')
            for card in self.pricecard_set.all():
                card.countries.add(country)


class SubscriptionFactory(factory.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    plan = factory.SubFactory(SubscriptionPlanFactory)
    valid_from = factory.Faker("past_date")
    status = Subscription.STATUS_ACTIVE
    payment_method = factory.SubFactory(
        'payments.tests.factories.PaymentMethodFactory',
        user=factory.SelfAttribute('..user'),
    )
    provider = Subscription.PROVIDER_ADYEN

    class Meta:
        model = Subscription


class IntroductoryPriceCardFactory(factory.DjangoModelFactory):
    class Meta:
        model = IntroductoryPriceCard

    plan = factory.SubFactory(SubscriptionPlanFactory)
    price = factory.fuzzy.FuzzyDecimal(1, 1000, precision=2)
    currency = factory.SubFactory(CurrencyFactory)
    start_date = factory.Faker("past_date")
    end_date = factory.Faker("future_date")

    @factory.post_generation
    def countries(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for country in extracted:
                self.countries.add(country)


class PriceCardFactory(factory.DjangoModelFactory):
    class Meta:
        model = PriceCard

    plan = factory.SubFactory(SubscriptionPlanFactory)
    price = factory.fuzzy.FuzzyDecimal(1, 1000, precision=2)
    currency = factory.SubFactory(CurrencyFactory)

    @factory.post_generation
    def countries(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for country in extracted:
                self.countries.add(country)
