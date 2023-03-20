import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from amuse.analytics import update_is_pro_state
from amuse.db.decorators import with_history
from subscriptions.managers import (
    SubscriptionManager,
    SubscriptionPlanManager,
    PriceCardManager,
    IntroductoryPriceCardManager,
)
from users.models import User, UserMetadata

logger = logging.getLogger(__name__)


@with_history
class SubscriptionPlan(models.Model):
    TIER_PLUS = 1
    TIER_PRO = 2

    TIER_CHOICES = (
        (TIER_PLUS, "Amuse PLUS subscription tier"),
        (TIER_PRO, "Amuse PRO subscription tier"),
    )

    name = models.CharField(max_length=64, blank=False)
    period = models.IntegerField(
        help_text="Number of months of pro membership granted by this type of subscription. If left blank it is a perpetual subscription.",
        null=True,
        blank=True,
    )
    trial_days = models.IntegerField(
        help_text="Number of free trial days granted at beginning of subscription",
        default=0,
    )
    grace_period_days = models.IntegerField(
        help_text="Number of days subscription remains active if payment fails",
        default=0,
    )
    is_public = models.BooleanField(
        default=False,
        help_text="If checked users can see and purchase this subscription",
        db_index=True,
    )
    apple_product_id = models.CharField(max_length=255, blank=True, default='')
    apple_product_id_notrial = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Users that are not eligible for trial will be put on this plan',
    )
    apple_product_id_introductory = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Users that are eligible for introductory offers will be put on this plan',
    )
    google_product_id = models.CharField(max_length=255, blank=True, default='')
    google_product_id_trial = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Users that are eligible for trial will be put on this plan',
    )
    google_product_id_introductory = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Users that are eligible for introductory offers will be put on this plan',
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    tier = models.PositiveSmallIntegerField(choices=TIER_CHOICES, default=TIER_PRO)

    objects = SubscriptionPlanManager()

    def __str__(self):
        return self.name

    def get_introductory_price_card(self, country_code, date=timezone.now().date()):
        introductory_cards = IntroductoryPriceCard.objects.active(date).filter(
            plan=self, countries__code=country_code
        )

        if introductory_cards.count() > 1:
            logger.error(
                f'More than one IntroductoryPriceCard found for Plan {self.name} (id={self.pk}) and Country {country_code}'
            )
            return None

        return introductory_cards.first()

    def get_price_card(self, country="US", use_intro_price=False, *args, **kwargs):
        """
        Returns IntroductoryPriceCard if use_intro_card flag is True AND if IntroductoryPriceCard exists.
        Otherwise, PriceCard is returned.
        """
        card = None
        if use_intro_price:
            card = self.get_introductory_price_card(country, *args, **kwargs)

        if card is None:
            card = self._get_price_card(country, *args, **kwargs)

        return card

    def _get_price_card(self, country="US", *args, **kwargs):
        cards = self.pricecard_set.filter(countries__code=country)

        # if no cards exist for the specified Country, it's probably because we've sent
        # the default US plans since no localised plans are available.
        # switch to US PriceCard and continue without errors
        if not cards.exists():
            cards = self.pricecard_set.filter(countries__code="US")

        if cards.count() > 1:
            raise ValueError(
                f'More than one PriceCard found for Plan {self.name} (id={self.pk}) and Country {country}'
            )
        if not cards.exists():
            raise ValueError(
                f'No PriceCard found for Plan {self.name} (id={self.pk}) and Country {country}'
            )
        return cards.first()

    @property
    def has_trial_period(self):
        return self.trial_days > 0


class PriceCard(models.Model):
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    price = models.DecimalField(
        max_digits=8, decimal_places=2, help_text="Including VAT"
    )
    currency = models.ForeignKey('countries.Currency', on_delete=models.PROTECT)
    countries = models.ManyToManyField('countries.Country', blank=True)

    def __str__(self):
        return f'{self.plan.name} - {self.currency.code} {self.price}'

    @property
    def name(self):
        return str(self)

    @property
    def currency_and_price(self):
        return f'{self.currency.code} {self.price}'

    @property
    def price_adyen(self):
        price = int(self.price * pow(10, self.currency.decimals))
        return price

    @property
    def period_price(self):
        period = self.plan.period if self.plan.period else 1
        return str(round(self.price / period, 2))

    objects = PriceCardManager()


class IntroductoryPriceCard(PriceCard):
    period = models.PositiveSmallIntegerField(
        default=12,
        null=False,
        blank=False,
        help_text="New subscribers pay a introductory price for a specific duration (months). After this, they'll pay your regular price.",
    )
    start_date = models.DateField(
        null=False,
        blank=False,
        help_text='Introductory Price is available from this date.',
    )
    end_date = models.DateField(
        null=False,
        blank=False,
        help_text='Introductory Price is available until this date.',
    )

    def __str__(self):
        return f'[Intro. Price] {super(IntroductoryPriceCard, self).__str__()}'

    objects = IntroductoryPriceCardManager()


@with_history
class Subscription(models.Model):
    STATUS_CREATED = 0
    STATUS_ACTIVE = 1
    STATUS_EXPIRED = 2
    STATUS_ERROR = 4
    STATUS_GRACE_PERIOD = 6

    STATUS_CHOICES = (
        (STATUS_CREATED, "Created (pending first payment)"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired (was not renewed or was canceled)"),
        (STATUS_ERROR, "Error (first payment failed)"),
        (STATUS_GRACE_PERIOD, "In expiry grace period (due to failed payment)"),
    )

    VALID_STATUSES = (STATUS_ACTIVE, STATUS_EXPIRED)

    PROVIDER_ADYEN = 1
    PROVIDER_IOS = 2
    PROVIDER_GOOGLE = 3
    PROVIDER_VIP = 4
    PROVIDER_CHOICES = (
        (PROVIDER_ADYEN, "Adyen"),
        (PROVIDER_IOS, "iOS in-app"),
        (PROVIDER_GOOGLE, "Google in-app"),
        (PROVIDER_VIP, "VIP"),
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    valid_from = models.DateField(db_index=True)
    valid_until = models.DateField(
        null=True, blank=True, help_text="Only ended subscriptions have this set"
    )
    grace_period_until = models.DateField(
        null=True,
        blank=True,
        help_text="Will retry renewal payments and consider Subscription as active until this date",
    )
    status = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICES, default=STATUS_CREATED
    )
    provider = models.PositiveSmallIntegerField(
        choices=PROVIDER_CHOICES, default=PROVIDER_ADYEN
    )

    payment_method = models.ForeignKey(
        'payments.PaymentMethod', on_delete=models.SET_NULL, null=True, blank=True
    )
    free_trial_from = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Free Trial start date. Always used in pair with 'Free Trial Until'.",
    )
    free_trial_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Free Trial start date. Always used in pair with 'Free Trial From'.",
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = SubscriptionManager()

    def __str__(self):
        return "%s - %s" % (self.user, self.plan)

    @property
    def paid_until(self):
        if self.is_free:
            return None

        latest_payment = self.latest_payment()
        if latest_payment:
            return latest_payment.paid_until.date()
        elif self.valid_until:
            return self.valid_until
        else:
            return self.valid_from + relativedelta(months=self.plan.period)

    @property
    def is_free(self):
        return self.plan.pricecard_set.filter(price=0).exists()

    @property
    def payment_method_expiry_date(self):
        return self.payment_method and self.payment_method.expiry_date

    @property
    def payment_method_method(self):
        return self.payment_method and self.payment_method.method

    @property
    def payment_method_summary(self):
        return self.payment_method and self.payment_method.summary

    def clean(self):
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError({"valid_until": "Must be after 'valid_from'"})

    def latest_payment(self, allow_failed=False, allow_not_sent=False, allow_auth=True):
        PaymentTransaction = self.paymenttransaction_set.model

        statuses = [PaymentTransaction.STATUS_APPROVED]
        if allow_failed:
            statuses += [
                PaymentTransaction.STATUS_PENDING,
                PaymentTransaction.STATUS_DECLINED,
                PaymentTransaction.STATUS_CANCELED,
                PaymentTransaction.STATUS_ERROR,
            ]
        if allow_not_sent:
            statuses += [PaymentTransaction.STATUS_NOT_SENT]

        types = [
            PaymentTransaction.TYPE_PAYMENT,
            PaymentTransaction.TYPE_FREE_TRIAL,
            PaymentTransaction.TYPE_INTRODUCTORY_PAYMENT,
        ]
        if allow_auth:
            types += [PaymentTransaction.TYPE_AUTHORISATION]

        payments = self.paymenttransaction_set.filter(
            status__in=statuses, type__in=types
        )
        return payments.order_by("-created").first()

    def is_free_trial(self):
        if self.free_trial_from is None:
            return False

        if self.free_trial_until is None:
            return False

        return True

    def is_free_trial_active(self):
        if self.status not in [
            Subscription.STATUS_ACTIVE,
            Subscription.STATUS_GRACE_PERIOD,
        ]:
            return False

        if not self.is_free_trial():
            return False

        return self.free_trial_from < timezone.now() < self.free_trial_until

    def get_google_product_id(self):
        if self.provider != Subscription.PROVIDER_GOOGLE:
            return None

        payment = self.paymenttransaction_set.filter(
            customer_payment_payload__isnull=False
        ).first()
        if payment is None:
            return None

        return payment.customer_payment_payload.get('google_subscription_id', None)

    def get_current_plan(self):
        PaymentTransaction = self.paymenttransaction_set.model
        latest_payment = (
            self.paymenttransaction_set.filter(
                status=PaymentTransaction.STATUS_APPROVED,
                type=PaymentTransaction.TYPE_PAYMENT,
            )
            .order_by("-created")
            .first()
        )
        if not latest_payment:
            # Trial user has no payments, and plan is always whatever was AUTH:ed first
            payment_authorisation = (
                self.paymenttransaction_set.filter(
                    status=PaymentTransaction.STATUS_APPROVED,
                    type=PaymentTransaction.TYPE_AUTHORISATION,
                )
                .order_by("created")
                .first()
            )
            if payment_authorisation:
                latest_payment = payment_authorisation

        if latest_payment:
            return latest_payment.plan

        # Free pro plans are not re-activatable so just return current plan
        return self.plan

    def get_next_plan(self):
        valid_plan_changes = self.plan_changes.filter(
            valid=True, completed=False
        ).last()
        if valid_plan_changes:
            return valid_plan_changes.new_plan
        return self.plan

    def apple_receipt(self):
        PaymentTransaction = self.paymenttransaction_set.model
        payments = self.paymenttransaction_set.filter(
            status=PaymentTransaction.STATUS_APPROVED,
            type__in=(
                PaymentTransaction.TYPE_AUTHORISATION,
                PaymentTransaction.TYPE_PAYMENT,
            ),
        )
        if not payments:
            logger.warning(f"Apple subscription {self.pk} has no valid payments")
            return
        first_payment = payments.order_by("created").first()
        customer_payload = first_payment.customer_payment_payload
        if customer_payload is not None and "receipt_data" in customer_payload.keys():
            return customer_payload.get('receipt_data')

    def allowed_grace_period_until(self):
        return self.paid_until + timedelta(days=self.plan.grace_period_days)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.__subscription_post_save()

    def __update_segment_user(self):
        if not settings.SEGMENT_UPDATE_IS_PRO_STATE:
            return

        try:
            if not self.user or self.user.id is None:
                return

            update_is_pro_state(self.user)
        except Exception as ex:
            logger.warning(f'Unable to update Segment User: {self.user.id}', ex)

    def __clear_user_is_pro_cache(self):
        if self.user and hasattr(self.user, 'is_pro'):
            del self.user.is_pro

    def __subscription_post_save(self):
        self.__clear_user_is_pro_cache()
        self.__update_segment_user()

        try:
            if self.user_id and self.user.zendesk_id and not settings.DEBUG:
                from amuse.tasks import zendesk_create_or_update_user

                zendesk_create_or_update_user.delay(self.user_id)

            # reset main_artist_profile on PRO Subscription creation
            if (
                self
                and self.status == Subscription.STATUS_ACTIVE
                and self.plan.tier == SubscriptionPlan.TIER_PRO
            ):
                self.user.userartistrole_set.filter(main_artist_profile=True).update(
                    main_artist_profile=False
                )
        except Exception as e:
            logger.warning(
                'Unable to update Zendesk User status for '
                'Subscription: {} and User: {} with error: {}'.format(
                    self.pk, self.user_id, str(e)
                )
            )


class SubscriptionPlanChanges(models.Model):
    subscription = models.ForeignKey(
        'Subscription', on_delete=models.DO_NOTHING, related_name='plan_changes'
    )
    current_plan = models.ForeignKey(
        'SubscriptionPlan', on_delete=models.DO_NOTHING, related_name='current_plans'
    )
    new_plan = models.ForeignKey(
        'SubscriptionPlan', on_delete=models.DO_NOTHING, related_name='new_plans'
    )
    completed = models.BooleanField(
        default=False, help_text='Set to True once plan change is completed'
    )
    valid = models.BooleanField(
        default=True, help_text='Used to invalidate plan change'
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        unique_together = ('subscription', 'current_plan', 'new_plan')
