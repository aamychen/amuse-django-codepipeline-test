from django.utils import timezone

from amuse.settings.constants import NONLOCALIZED_PAYMENTS_COUNTRY as DEFAULT_COUNTRY

# from .s2s import send_s2s
from amuse.vendor.appsflyer.s2s import send_s2s

tiers = {1: 'Boost', 2: 'Pro'}


def _create_subscription_data(subscription, ip, country):
    payment = subscription.latest_payment()

    tier_name = tiers.get(subscription.plan.tier, subscription.plan.tier)

    currency_code = payment.currency.code

    price = str(payment.amount)
    return {
        'currency': currency_code,
        'price': price,
        'plan_name': subscription.plan.name,
        'ip': ip,
        'user_first_name': subscription.user.first_name,
        'subscription_plan_name': subscription.plan.name,
        'subscription_plan_price': f'{payment.currency.code} {str(payment.amount)}',
        'renewal_date': subscription.paid_until.isoformat(),
        'tier': tier_name,
        'product': {
            'name': subscription.plan.name,
            'product_id': subscription.plan_id,
            'quantity': 1,
        },
        'revenue': price,
        'total': price,
        'af_revenue': price,
        'af_currency': currency_code,
        'af_content_id': subscription.plan_id,
        'af_quantity': 1,
        'platform': payment.get_platform_display(),
    }


def email_verified(device, user_id):
    send_s2s(device=device, user_id=user_id, event_name='Email Verified', data={})


def ffwd_started(device, user, withdrawal_amount):
    send_s2s(
        device=device,
        user_id=user.id,
        event_name='Ffwd Started',
        data={'withdrawal_amount': str(withdrawal_amount)},
    )


def login_succeeded(device, user, data):
    send_s2s(device=device, user_id=user.id, event_name='login_succeeded', data=data)


def royalty_advance_notification(device, user_id, offer_type, price):
    send_s2s(
        device=device,
        user_id=user_id,
        event_name='ffwd_new_offer',
        data={'price': price, 'offer_type': offer_type},
    )


def split_accepted(device, split):
    send_s2s(
        device=device,
        user_id=split.user_id,
        event_name='split_accepted',
        data={'split_rate': str(split.rate), 'song_name': split.song.name},
    )


def split_invites_expired(device, user_id, song_name):
    send_s2s(
        device=device,
        user_id=user_id,
        event_name='split_invites_expired',
        data={'song_name': song_name},
    )


def subscription_canceled(device, subscription, ip):
    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='subscription_cancelled',
        data={
            'ip': ip,
            'plan_name': subscription.plan.name,
            'user_first_name': subscription.user.first_name,
            'subscription_plan_end_date': subscription.valid_until.isoformat(),
        },
    )


def subscription_changed(
    device, subscription, previous_plan, new_plan, ip, country=DEFAULT_COUNTRY
):
    card = new_plan.get_price_card(country=country)
    previous_card = previous_plan.get_price_card(country=country)

    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='subscription_plan_changed_confirmation',
        data={
            'currency': card.currency.code,
            'price': str(card.price),
            'plan_name': subscription.plan.name,
            'ip': ip,
            'current_subscription_plan_name': previous_plan.name,
            'current_subscription_plan_price': previous_card.currency_and_price,
            'date_when_new_plan_will_become_active': subscription.paid_until.isoformat(),
            'new_subscription_plan_name': new_plan.name,
            'new_subscription_plan_price': card.currency_and_price,
            'user_first_name': subscription.user.first_name,
            'product': {
                'name': new_plan.name,
                'product_id': new_plan.pk,
                'quantity': 1,
            },
            'revenue': str(card.price),
            'total': str(card.price),
        },
    )


def subscription_tier_upgraded(
    device, subscription, previous_plan, ip, country=DEFAULT_COUNTRY
):
    """Special case of Subscription plan change, when User upgrades their subscription
    tier
    """
    previous_card = previous_plan.get_price_card(country=country)
    payment = subscription.latest_payment()

    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='subscription_plan_changed_confirmation',
        data={
            'currency': payment.currency.code,
            'price': str(payment.amount),
            'plan_name': subscription.plan.name,
            'ip': ip,
            'current_subscription_plan_name': previous_plan.name,
            'current_subscription_plan_price': previous_card.currency_and_price,
            'date_when_new_plan_will_become_active': timezone.now().date().isoformat(),
            'new_subscription_plan_name': subscription.plan.name,
            'new_subscription_plan_price': f'{payment.currency.code} {payment.amount}',
            'user_first_name': subscription.user.first_name,
            'product': {
                'name': subscription.plan.name,
                'product_id': subscription.plan_id,
                'quantity': 1,
            },
            'revenue': str(payment.amount),
            'total': str(payment.amount),
        },
    )


def subscription_new_intro_started(device, subscription, ip, country=DEFAULT_COUNTRY):
    data = _create_subscription_data(subscription, ip, country)

    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='Subscription IntroStarted',
        data=data,
    )


def subscription_new_started(device, subscription, ip, country=DEFAULT_COUNTRY):
    data = _create_subscription_data(subscription, ip, country)

    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='Subscription Started',
        data=data,
    )


def subscription_payment_method_changed(device, subscription, ip):
    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='payment_method_updated',
        data={
            'ip': ip,
            'user_first_name': subscription.user.first_name,
            'subscription_plan_name': subscription.plan.name,
        },
    )


def subscription_payment_method_expired(device, subscription, country=DEFAULT_COUNTRY):
    card = subscription.plan.get_price_card(country)
    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='payment_error_card_expired',
        data={
            'user_first_name': subscription.user.first_name,
            'subscription_plan_name': subscription.plan.name,
            'subscription_plan_price': card.currency_and_price,
            'subscription_plan_grace_period': subscription.grace_period_until.isoformat(),
        },
    )


def subscription_renewal_error(device, subscription, country=DEFAULT_COUNTRY):
    card = subscription.plan.get_price_card(country)

    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='payment_error_generic',
        data={
            'user_first_name': subscription.user.first_name,
            'subscription_plan_name': subscription.plan.name,
            'subscription_plan_price': card.currency_and_price,
            'subscription_plan_grace_period': subscription.grace_period_until.isoformat(),
        },
    )


def subscription_renewal_error_lack_of_funds(
    device, subscription, country=DEFAULT_COUNTRY
):
    card = subscription.plan.get_price_card(country)
    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='payment_error_lack_of_funds',
        data={
            'user_first_name': subscription.user.first_name,
            'subscription_plan_name': subscription.plan.name,
            'subscription_plan_price': card.currency_and_price,
            'subscription_plan_grace_period': subscription.grace_period_until.isoformat(),
        },
    )


def subscription_successful_renewal(device, subscription, amount, currency_code):
    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='subscription_successful_renewal',
        data={
            'currency': currency_code,
            'price': str(amount),
            'plan_name': subscription.plan.name,
            'current_subscription_plan_name': subscription.plan.name,
            'current_subscription_plan_price': f'{currency_code} {amount}',
            'user_first_name': subscription.user.first_name,
            'product': {
                'name': subscription.plan.name,
                'product_id': subscription.plan_id,
                'quantity': 1,
            },
            'revenue': str(amount),
            'total': str(amount),
        },
    )


def subscription_trial_started(device, subscription, ip, country=DEFAULT_COUNTRY):
    data = _create_subscription_data(subscription, ip, country)

    send_s2s(
        device=device,
        user_id=subscription.user_id,
        event_name='Subscription TrialStarted',
        data=data,
    )


def s4a_connected(device, user_id, artist_id):
    send_s2s(
        device=device,
        user_id=user_id,
        event_name='s4a_complete',
        data={'artist_id': artist_id},
    )


def signup_completed(
    device, user_id, platform_name, detected_user_country, signup_path
):
    payload = {
        "country": detected_user_country,
        "platform": platform_name,
        "signup_path": signup_path,
    }
    send_s2s(
        device=device, user_id=user_id, event_name='Signup Completed', data=payload
    )


def rb_successful(device, user_id, platform_name, detected_user_country, event_data):
    event_data["release_date"] = event_data["release_date"].isoformat()
    payload = {"country": detected_user_country, "platform": platform_name}
    payload.update(event_data)
    send_s2s(device=device, user_id=user_id, event_name='Rb Successful', data=payload)
