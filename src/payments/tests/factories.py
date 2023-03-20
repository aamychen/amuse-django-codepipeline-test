from datetime import timezone
from decimal import Decimal

import factory

from countries.tests.factories import CountryFactory, CurrencyFactory
from payments.models import PaymentMethod, PaymentTransaction
from subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory
from users.tests.factories import UserFactory


class PaymentMethodFactory(factory.DjangoModelFactory):
    expiry_date = factory.Faker("future_date")
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = PaymentMethod


class PaymentTransactionFactory(factory.DjangoModelFactory):
    external_transaction_id = factory.Sequence("trans_{0}".format)
    amount = factory.fuzzy.FuzzyDecimal(1, 999, precision=2)
    vat_amount = Decimal("0.0")
    vat_percentage = Decimal("0.0")
    currency = factory.SubFactory(CurrencyFactory)
    country = factory.SubFactory(CountryFactory)
    status = PaymentTransaction.STATUS_APPROVED
    paid_until = factory.Faker("future_datetime", tzinfo=timezone.utc)

    type = PaymentTransaction.TYPE_PAYMENT

    payment_method = factory.SubFactory(PaymentMethodFactory)
    plan = factory.SubFactory(SubscriptionPlanFactory)
    subscription = factory.SubFactory(
        SubscriptionFactory,
        payment_method=factory.SelfAttribute("..payment_method"),
        plan=factory.SelfAttribute("..plan"),
        user=factory.SelfAttribute("..user"),
    )
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = PaymentTransaction
