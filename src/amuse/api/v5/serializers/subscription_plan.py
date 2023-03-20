import logging
from decimal import Decimal

from rest_framework import serializers
from rest_framework.exceptions import APIException

from subscriptions.models import SubscriptionPlan, IntroductoryPriceCard

logger = logging.getLogger(__name__)


class CurrentSubscriptionPlanSerializer(serializers.ModelSerializer):
    """For current Subscriptions we use the latest transaction to fetch the User's
    current Country and Currency settings"""

    country = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    price_display = serializers.SerializerMethodField()
    period_price = serializers.SerializerMethodField()
    period_price_display = serializers.SerializerMethodField()
    tier = serializers.IntegerField()

    google_product_id = serializers.SerializerMethodField()
    apple_product_id = serializers.SerializerMethodField()

    def get_country(self, plan):
        return Common.get_country(self.context, plan)

    def get_currency(self, plan):
        user = self.context['request'].user
        latest_payment = user.current_entitled_subscription().latest_payment()
        if latest_payment:
            return user.current_entitled_subscription().latest_payment().currency.code

        # VIP users have subscriptions, without any transaction.
        # For VIP users we will return default USD currency
        return 'USD'

    def get_price(self, plan):
        currency = self.get_currency(plan)

        # because PRO Yearly Campaign had only USD as a Currency option we have to check
        # if we have a PriceCard for this Plan with the correct Currency
        price_card = plan.pricecard_set.filter(currency__code=currency).first()
        if price_card:
            return str(price_card.price)

        # no PriceCard found, let's pull data from the latest transaction
        user = self.context['request'].user
        subscription = user.current_entitled_subscription()
        latest_payment = subscription.latest_payment()
        if latest_payment:
            return str(latest_payment.amount)

        # no PriceCard and no successful transactions, something is definitely wrong
        # log the error and send a helpful message to the clients
        logger.error(
            f'No PriceCard and no successful transaction found for Subscription {subscription.pk}'
        )
        raise APIException(
            'There is an error with your Subscription. Please contact Amuse support.'
        )

    def get_price_display(self, plan):
        return Common.format_price(self.get_price(plan), self.get_currency(plan))

    def get_period_price(self, plan):
        currency = self.get_currency(plan)

        # because PRO Yearly Campaign had only USD as a Currency option we have to check
        # if we have a PriceCard for this Plan with the correct Currency
        price_card = plan.pricecard_set.filter(currency__code=currency).first()
        if price_card:
            return str(price_card.period_price)

        # no PriceCard found, let's pull data from the latest transaction
        user = self.context['request'].user
        subscription = user.current_entitled_subscription()
        latest_payment = subscription.latest_payment()
        if latest_payment:
            price = latest_payment.amount
            period = subscription.plan.period if subscription.plan.period else 1
            return str(round(price / period, 2))

        # no PriceCard and no successful transactions, something is definitely wrong
        # log the error and send a helpful message to the clients
        logger.error(
            f'No PriceCard and no successful transaction found for Subscription {subscription.pk}'
        )
        raise APIException(
            'There is an error with your Subscription. Please contact Amuse support.'
        )

    def get_period_price_display(self, plan):
        return Common.format_price(self.get_period_price(plan), self.get_currency(plan))

    def get_google_product_id(self, plan):
        user = self.context['request'].user
        if user.is_free_trial_active():
            return plan.google_product_id_trial

        sub = user.current_entitled_subscription()
        if sub is None:
            return plan.google_product_id

        google_product_id = sub.get_google_product_id()
        if google_product_id:
            return google_product_id

        return plan.google_product_id

    def get_apple_product_id(self, plan):
        return Common.get_apple_product_id(self.context, plan)

    class Meta:
        model = SubscriptionPlan
        fields = (
            'id',
            'name',
            'price',
            'period_price',
            'price_display',
            'period_price_display',
            'currency',
            'period',
            'trial_days',
            'apple_product_id',
            'google_product_id',
            'country',
            'tier',
        )


class IntroductoryPriceCardSerializer(serializers.ModelSerializer):
    currency = serializers.SerializerMethodField()
    price_display = serializers.SerializerMethodField()
    introductory_price_id = serializers.SerializerMethodField()

    def get_currency(self, card):
        return card.currency.code

    def get_price_display(self, card):
        return Common.format_price(card.price, card.currency.code)

    def get_introductory_price_id(self, card):
        return card.id

    class Meta:
        model = IntroductoryPriceCard
        fields = (
            'introductory_price_id',
            'price',
            'period',
            'price_display',
            'currency',
            'period',
            'start_date',
            'end_date',
        )


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    country = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    price_display = serializers.SerializerMethodField()
    period_price = serializers.SerializerMethodField()
    period_price_display = serializers.SerializerMethodField()
    tier = serializers.IntegerField()
    apple_product_id = serializers.SerializerMethodField()
    introductory_price = serializers.SerializerMethodField()

    def get_country(self, plan):
        return Common.get_country(self.context, plan)

    def get_currency(self, plan):
        country_code = Common.get_country_code(self.context, plan)
        return plan.get_price_card(country_code).currency.code

    def get_price(self, plan):
        country_code = Common.get_country_code(self.context, plan)
        return str(plan.get_price_card(country_code).price)

    def get_price_display(self, plan):
        country_code = Common.get_country_code(self.context, plan)
        return Common.format_price(
            plan.get_price_card(country_code).price,
            plan.get_price_card(country_code).currency.code,
        )

    def get_period_price(self, plan):
        country_code = Common.get_country_code(self.context, plan)
        return plan.get_price_card(country_code).period_price

    def get_period_price_display(self, plan):
        country_code = Common.get_country_code(self.context, plan)
        return Common.format_price(
            plan.get_price_card(country_code).period_price,
            plan.get_price_card(country_code).currency.code,
        )

    def get_apple_product_id(self, plan):
        return Common.get_apple_product_id(self.context, plan)

    def get_introductory_price(self, plan):
        if not self.show_introductory_price():
            return None

        country = Common.get_country(self.context, plan)
        introductory_price_card = plan.get_introductory_price_card(country)
        if introductory_price_card:
            return IntroductoryPriceCardSerializer(
                introductory_price_card, context=self.context
            ).data

        return None

    def show_introductory_price(self):
        request = self.context.get('request')
        if request is None:
            return False

        user = request.user
        if user is None:
            return True

        if user.is_anonymous:
            return True

        return user.is_introductory_price_eligible()

    class Meta:
        model = SubscriptionPlan
        fields = (
            'id',
            'name',
            'price',
            'period_price',
            'price_display',
            'period_price_display',
            'currency',
            'period',
            'trial_days',
            'apple_product_id',
            'apple_product_id_introductory',
            'google_product_id',
            'google_product_id_trial',
            'google_product_id_introductory',
            'country',
            'tier',
            'introductory_price',
        )


class Common(object):
    @staticmethod
    def get_country_code(context, plan):
        if 'country' in context:
            return context['country']

        user = context['request'].user

        latest_payment = user.current_entitled_subscription().latest_payment()
        if latest_payment:
            return user.current_entitled_subscription().latest_payment().country.code

        # VIP users have subscriptions, without any transaction.
        # For VIP users we will return default US country code
        return 'US'

    @staticmethod
    def get_country(context, plan):
        return Common.get_country_code(context, plan)

    @staticmethod
    def format_price(amount, currency_code):
        price = '{:f}'.format(Decimal(amount).normalize())
        return f'{currency_code} {price}'

    @staticmethod
    def get_apple_product_id(context, plan):
        if 'request' not in context:
            return plan.apple_product_id

        user = context['request'].user
        if user.is_anonymous:
            return plan.apple_product_id
        return plan.apple_product_id_notrial
