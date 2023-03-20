from django.db import models
from django.utils import timezone


class SubscriptionManager(models.Manager):
    def active(self):
        return self.get_queryset().filter(
            status__in=(self.model.STATUS_ACTIVE, self.model.STATUS_GRACE_PERIOD)
        )

    def active_adyen(self):
        '''Returns subscriptions that should be renewed using Adyen'''
        return self._active_by_provider(self.model.PROVIDER_ADYEN)

    def active_apple(self):
        '''Returns Apple that needss to be polled for renewal status'''
        return self._active_by_provider(self.model.PROVIDER_IOS)

    def active_for_date(self, date):
        model = self.model
        return (
            self.get_queryset()
            .filter(valid_from__lte=date)
            .filter(
                (
                    models.Q(status__in=model.VALID_STATUSES)
                    & (models.Q(valid_until=None) | models.Q(valid_until__gte=date))
                )
                | (
                    models.Q(status=model.STATUS_GRACE_PERIOD)
                    & models.Q(grace_period_until__gte=date)
                )
            )
        )

    def _active_by_provider(self, provider):
        model = self.model
        return (
            self.get_queryset()
            .exclude(plan__pricecard__price=0)
            .filter(provider=provider)
            .filter(
                models.Q(status=model.STATUS_ACTIVE, valid_until__isnull=True)
                | models.Q(status=model.STATUS_GRACE_PERIOD)
            )
        )

    def valid(self):
        """
        Since ACTIVE, GRACE and EXPIRED subscriptions are/were active at some point of time, we are considering them as valid.
        """
        return self.get_queryset().filter(
            status__in=(
                self.model.STATUS_ACTIVE,
                self.model.STATUS_GRACE_PERIOD,
                self.model.STATUS_EXPIRED,
            )
        )


class SubscriptionPlanManager(models.Manager):
    def get_by_product_id(self, apple_product_id):
        return (
            self.get_queryset()
            .filter(
                models.Q(apple_product_id=apple_product_id)
                | models.Q(apple_product_id_notrial=apple_product_id)
                | models.Q(apple_product_id_introductory=apple_product_id)
            )
            .first()
        )

    def get_by_google_product_id(self, google_product_id):
        return (
            self.get_queryset()
            .filter(
                models.Q(google_product_id=google_product_id)
                | models.Q(google_product_id_trial=google_product_id)
                | models.Q(google_product_id_introductory=google_product_id)
            )
            .first()
        )


class PriceCardManager(models.Manager):
    def get_queryset(self):
        """
        Due to specific way how Django works with model inheritance, we have to
        exclude inherited objects from the results.
        """
        return (
            super(PriceCardManager, self)
            .get_queryset()
            .filter(introductorypricecard__isnull=True)
        )


class IntroductoryPriceCardManager(models.Manager):
    def get_queryset(self):
        return super(IntroductoryPriceCardManager, self).get_queryset()

    def active(self, date=timezone.now().date()):
        return self.get_queryset().filter(start_date__lte=date, end_date__gte=date)
