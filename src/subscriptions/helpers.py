import logging
import math
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from amuse.analytics import subscription_successful_renewal
from amuse.vendor.adyen import renew_subscription
from amuse.vendor.apple.exceptions import (
    DuplicateAppleTransactionIDError,
    MaxRetriesExceededError,
    UnknownAppleError,
)
from amuse.vendor.apple.subscriptions import AppleReceiptValidationAPIClient
from amuse.vendor.zendesk.api import update_users as update_zendesk_users
from payments.helpers import create_apple_payment
from payments.models import PaymentTransaction
from subscriptions.models import Subscription, SubscriptionPlan

logger = logging.getLogger(__name__)


def renew_adyen_subscriptions(is_dry_run):
    today = timezone.now().date()
    renew_count = 0
    error_count = 0
    active_subscriptions = Subscription.objects.active_adyen()

    for subscription in active_subscriptions:
        successful_payment = subscription.latest_payment()

        if not successful_payment:
            logger.info(
                "Skipping and setting to ERROR subscription with id %s because it has no Adyen payments"
                % subscription.pk
            )
            subscription.status = Subscription.STATUS_ERROR
            subscription.save()
            continue

        subscribed_until = successful_payment.paid_until.date()
        previous_payment = subscription.latest_payment(allow_failed=True)
        currency_code = previous_payment.currency.code
        if subscribed_until <= today:
            if is_dry_run:
                print("Would renew subscription with id %s" % subscription.pk)
                renew_count += 1
            else:
                renew_status = renew_subscription(subscription, currency_code)
                new_payment = subscription.latest_payment(allow_failed=True)
                _set_payment_category(previous_payment, new_payment)

                if renew_status['is_success']:
                    logger.info("Renewing subscription with id %s" % subscription.pk)
                    subscription_successful_renewal(
                        subscription, new_payment.amount, currency_code
                    )
                    renew_count += 1
                else:
                    logger.info(
                        "Error renewing subscription with id %s: %s"
                        % (subscription.pk, renew_status['error_message'])
                    )
                    error_count += 1

    if is_dry_run:
        print("Would renew %s subscriptions" % renew_count)
    else:
        error_message = ''
        if error_count > 0:
            error_message = '. Error renewing %s subscriptions' % error_count
        logger.info("Renewed %s subscriptions%s" % (renew_count, error_message))


def renew_apple_subscriptions(is_dry_run):
    error_count = 0
    renew_count = 0
    active_subscriptions = Subscription.objects.active_apple()

    for subscription in active_subscriptions:
        is_success = renew_apple_subscription(
            subscription, is_dry_run, platform=PaymentTransaction.PLATFORM_CRON
        )
        if is_success:
            renew_count += 1
        else:
            error_count += 1

    if is_dry_run:
        print("Would renew %s Apple subscriptions" % renew_count)
    else:
        logger.info("Renewed %s Apple subscriptions" % renew_count)
        error_message = ''
        if error_count > 0:
            error_message = '. Error renewing %s subscriptions' % error_count
        logger.info("Renewed %s Apple subscriptions%s" % (renew_count, error_message))


def renew_apple_subscription(subscription, is_dry_run, platform):
    today = timezone.now().date()
    latest_payment = subscription.latest_payment()

    if not latest_payment:
        logger.info(
            "Skipping subscription with id %s because it has no Apple payments"
            % subscription.pk
        )
        return False

    subscribed_until = latest_payment.paid_until.date()
    if subscribed_until <= today:
        if is_dry_run:
            print("Would renew Apple subscription with id %s" % subscription.pk)
            return True

        receipt = subscription.apple_receipt()
        if not receipt:
            return False
        client = AppleReceiptValidationAPIClient(receipt, max_retries=1)
        try:
            client.validate_receipt()
        except (UnknownAppleError, MaxRetriesExceededError) as e:
            return False

        plan = SubscriptionPlan.objects.get_by_product_id(client.get_product_id())
        country = latest_payment.country
        transaction_id = None
        try:
            transaction_id = client.get_transaction_id()
        except DuplicateAppleTransactionIDError:
            # If the latest transaction is a dupe this subscription has not been renewed,
            # leave it in grace period until expires job catches it or user renews
            return False

        amount = plan.get_price_card(country.code).price
        currency = plan.get_price_card(country.code).currency

        is_renewed = create_apple_payment(
            amount=amount,
            category=PaymentTransaction.CATEGORY_RENEWAL,
            country=country,
            external_transaction_id=transaction_id,
            paid_until=client.get_expires_date(),
            payment_method=latest_payment.payment_method,
            plan=plan,
            status=PaymentTransaction.STATUS_APPROVED,
            subscription=subscription,
            type=PaymentTransaction.TYPE_PAYMENT,
            user=subscription.user,
            vat_amount=country.vat_amount(plan.get_price_card(country.code).price),
            vat_percentage=country.vat_percentage,
            currency=currency,
            platform=platform,
        )
        if is_renewed:
            subscription_successful_renewal(subscription, amount, currency.code)
            if subscription.paid_until > today:
                subscription.status = Subscription.STATUS_ACTIVE
                subscription.valid_until = None
                subscription.grace_period_until = None
                subscription.plan = plan
                subscription.save()
                logger.info("Renewing Apple subscription with id %s" % subscription.pk)
                return True

    return False


def expire_subscriptions():
    today = timezone.now().date()
    users = []
    adyen_expired_count = 0

    expired_grace_period_subscriptions = (
        Subscription.objects.filter(provider=Subscription.PROVIDER_ADYEN)
        .filter(status=Subscription.STATUS_GRACE_PERIOD, grace_period_until__lt=today)
        .exclude(plan__pricecard__price=0)
        .select_related('user')
    )
    expired_grace_period_subscriptions.update(status=Subscription.STATUS_EXPIRED)
    adyen_expired_count += expired_grace_period_subscriptions.count()
    users += [subscription.user for subscription in expired_grace_period_subscriptions]

    expired_active_subscriptions = (
        Subscription.objects.filter(provider=Subscription.PROVIDER_ADYEN)
        .filter(
            status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_GRACE_PERIOD],
            valid_until__lt=today,
        )
        .exclude(plan__pricecard__price=0)
        .select_related('user', 'plan')
    )
    for subscription in expired_active_subscriptions:
        subscription.status = Subscription.STATUS_EXPIRED
        adyen_expired_count += 1
        users.append(subscription.user)
        subscription.save()

    logger.info('Expired %s Adyen subscriptions' % adyen_expired_count)

    apple_expired_count = 0
    apple_subscriptions = (
        Subscription.objects.active()
        .prefetch_related('paymenttransaction_set')
        .select_related('user', 'plan')
        .filter(provider=Subscription.PROVIDER_IOS)
        .filter(Q(valid_until=None) | Q(valid_until__lt=today))
        .exclude(plan__pricecard__price=0)
    )
    for subscription in apple_subscriptions:
        valid_until_passed = (
            subscription.valid_until and subscription.valid_until < today
        )
        paid_until = subscription.paid_until
        if not valid_until_passed and paid_until is None:
            logger.info('Apple subscription %s has no paid_until' % subscription.pk)
            continue
        if valid_until_passed or paid_until < today:
            subscription.valid_until = paid_until
            subscription.grace_period_until = paid_until + timedelta(
                days=subscription.plan.grace_period_days
            )
            if subscription.grace_period_until < today:
                subscription.status = Subscription.STATUS_EXPIRED
                apple_expired_count += 1
                users.append(subscription.user)
            else:
                subscription.status = Subscription.STATUS_GRACE_PERIOD
            subscription.save()

    logger.info('Expired %s Apple subscriptions' % apple_expired_count)

    expired_vip_count = 0
    expired_vip_subscriptions = Subscription.objects.filter(
        provider=Subscription.PROVIDER_VIP,
        status=Subscription.STATUS_ACTIVE,
        valid_until__lt=today,
    ).select_related('user')
    expired_vip_count += expired_vip_subscriptions.count()
    expired_vip_subscriptions.update(status=Subscription.STATUS_EXPIRED)
    users += [subscription.user for subscription in expired_vip_subscriptions]
    logger.info('Expired %s VIP subscriptions' % expired_vip_count)

    users_count = len(users)
    cache.set(key="users_downgraded-" + str(today), value=users, timeout=604800)
    if users_count > 0 and settings.ZENDESK_API_TOKEN:
        update_zendesk_users(users)
        logger.info('Updated %s Zendesk users' % users_count)


def _set_payment_category(previous_payment, new_payment):
    category = PaymentTransaction.CATEGORY_UNKNOWN

    if previous_payment.category == PaymentTransaction.CATEGORY_INITIAL:
        category = PaymentTransaction.CATEGORY_RENEWAL
    else:
        if previous_payment.paid_until == new_payment.paid_until:
            category = PaymentTransaction.CATEGORY_RETRY
        else:
            category = PaymentTransaction.CATEGORY_RENEWAL

    new_payment.category = category
    new_payment.save()


def calculate_tier_upgrade_price(subscription, new_plan):
    latest_payment = subscription.latest_payment(allow_auth=False)
    if not latest_payment:
        raise ValueError(
            f'No valid payments found for Subscription {subscription.pk}, unable to calculate Tier upgrade price'
        )

    currency = latest_payment.currency
    country = latest_payment.country

    # first figure out how many days are left in current subscription
    old_plan_price = latest_payment.amount

    last_day_paid = latest_payment.paid_until.date()
    first_day_paid = latest_payment.created.date()
    total_paid_days = (last_day_paid - first_day_paid).days
    today = timezone.now().date()

    days_left = max(0, (last_day_paid - today).days)
    days_used = min(total_paid_days, (today - first_day_paid).days)
    if total_paid_days != (days_used + days_left):
        raise ValueError(
            f'Dates do not match for Subscription {subscription.pk}: Total days: {total_paid_days}, Days used: {days_used}, Days left {days_left}, First day paid: {first_day_paid}, Last day paid: {last_day_paid}'
        )

    # now we can calculate how much money is left over
    price_per_day = old_plan_price / (days_used + days_left)
    leftover_amount = price_per_day * days_left

    # fetch full price for the new plan IN THE SAME CURRENCY - important!
    new_plan_price = get_price(new_plan, currency, country)

    # finally, deduct the refund price from new plan full price
    # and round down to nearest .99
    deducted_price = new_plan_price - leftover_amount
    if deducted_price == new_plan_price:  # sub was in grace period
        return new_plan_price, currency

    final_price = max(0, math.floor(deducted_price) - 1) + Decimal('0.99')
    return final_price, currency


def get_price(plan, currency, country):
    # in most cases, there should be 1 price card per currency
    price_cards = plan.pricecard_set.filter(currency=currency)

    # if there is more than one, we must also filter by country
    if price_cards.count() > 1:
        price_cards = price_cards.filter(countries=country)

    # if we still have more than one price card, we can't calculate the price
    if price_cards.count() > 1:
        raise ValueError(
            f'There are multiple PriceCards for Plan {plan.name} ({currency.code}, {country.code}), unable to calculate Tier upgrade price'
        )
    # if there's no price card present, we can't calculate the price
    elif not price_cards.exists():
        raise ValueError(
            f'There are no PriceCards for Plan {plan.name} ({currency.code}, {country.code}), unable to calculate Tier upgrade price'
        )
    else:
        return price_cards.first().price
