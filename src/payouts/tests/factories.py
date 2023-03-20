import factory
import json
from users.tests.factories import UserFactory
from payouts.models import (
    Provider,
    Payee,
    TransferMethod,
    Payment,
    Event,
    TransferMethodConfiguration,
)
from countries.tests.factories import CurrencyFactory, CountryFactory


class ProviderFactory(factory.DjangoModelFactory):
    name = "Hyperwallet Embedded straight-trough program"
    external_id = "prg-19d7ef5e-e01e-43bc-b271-79eef1062832"

    class Meta:
        model = Provider


class PayeeFactory(factory.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    provider = factory.SubFactory(ProviderFactory)
    external_id = "usr-f9154016-94e8-4686-a840-075688ac07b5"
    status = "PRE_ACTIVATED"
    verification_status = "NOT_REQUIRED"
    type = Payee.TYPE_INDIVIDUAL

    class Meta:
        model = Payee


class TransferMethodFactory(factory.DjangoModelFactory):
    payee = factory.SubFactory(PayeeFactory)
    external_id = "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
    type = "BANK_ACCOUNT"
    status = "ACTIVATED"
    provider = factory.SubFactory(ProviderFactory)
    currency = factory.SubFactory(CurrencyFactory)

    class Meta:
        model = TransferMethod


class PaymentFactory(factory.DjangoModelFactory):
    payee = factory.SubFactory(PayeeFactory)
    external_id = "pmt-87939c73-ff0a-4011-970e-3de855347ea7"
    transfer_method = factory.SubFactory(TransferMethodFactory)
    currency = factory.SubFactory(CurrencyFactory)
    amount = factory.fuzzy.FuzzyDecimal(1, 999, precision=2)
    status = "COMPLETED"

    class Meta:
        model = Payment


class EventFactory(factory.DjangoModelFactory):
    object_id = "trm-56b976c5-26b2-42fa-87cf-14b3366673c6"
    reason = "WEBHOOK"
    initiator = "SYSTEM"
    payload = json.dumps(
        {
            "token": "wbh-9e350bf5-854e-4326-9400-611a5c17d8b9",
            "type": "USERS.CREATED",
            "createdOn": "2019-09-13T12:49:43",
            "object": {
                "token": "usr-de305d54-75b4-432b-aac2-eb6b9e546014",
                "status": "PRE_ACTIVATED",
                "createdOn": "2019-01-01T16:01:30",
                "clientUserId": "C301245",
                "profileType": "INDIVIDUAL",
                "firstName": "John",
                "lastName": "Smith",
                "email": "johnsmith@yourbrandhere.com",
                "addressLine1": "123 Main Street",
                "city": "New York",
                "stateProvince": "NY",
                "country": "US",
                "postalCode": "10016",
                "language": "en",
                "programToken": "prg-eb305d54-00b4-432b-eac2-ab6b9e123409",
            },
        }
    )

    class Meta:
        model = Event


class TransferMethodCofigurationFactory(factory.DjangoModelFactory):
    provider = factory.SubFactory(ProviderFactory)
    currency = factory.SubFactory(CurrencyFactory)
    country = factory.SubFactory(CountryFactory)
    type = "BANK_ACCOUNT"
    fee = json.dumps({"absolute": 2, "percent": 1})
    limits = json.dumps({"max": 100000, "min": 35})

    class Meta:
        model = TransferMethodConfiguration
