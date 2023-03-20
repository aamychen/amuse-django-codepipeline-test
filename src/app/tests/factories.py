import factory.fuzzy

from ..models.deliveries import Delivery


class DeliveryFactory(factory.DjangoModelFactory):
    class Meta:
        model = Delivery

    release = factory.SubFactory('releases.tests.factories.ReleaseFactory')
