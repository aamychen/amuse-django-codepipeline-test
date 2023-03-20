import logging
from datetime import datetime

from django.utils import timezone
from waffle import sample_is_active

from amuse.settings.constants import NONLOCALIZED_PAYMENTS_COUNTRY as DEFAULT_COUNTRY
from amuse.vendor.segment import track as track_sync, identify as identify_sync
from amuse.vendor.segment.tasks import (
    send_segment_track as track_async,
    send_segment_identify as identify_async,
)

logger = logging.getLogger(__name__)

tiers = {0: 'Free', 1: 'Boost', 2: 'Pro'}

WAFFLE_SAMPLE_KEY = 'segment:celery:enabled'


def email_verified(user_id):
    logger.info(f'Segment "Email Verified" event for user_id: %s', user_id)
    track(user_id, 'Email Verified', properties={})


def ffwd_started(user_id, withdrawal_amount):
    data = {'withdrawal_amount': withdrawal_amount}

    logger.info(
        'Segment "Ffwd Started" event for user_id: %s, withdrawal_amount: %s',
        user_id,
        withdrawal_amount,
    )
    track(user_id, 'Ffwd Started', properties=data)


def update_is_pro_state(user):
    if not user or user.id is None:
        return

    identify(user.id, {'is_pro': user.is_pro})


def subscription_renewal_error_lack_of_funds(subscription, country=DEFAULT_COUNTRY):
    _subscription_renewal_error(subscription, 'payment_error_lack_of_funds', country)


def subscription_payment_method_expired(subscription, country=DEFAULT_COUNTRY):
    _subscription_renewal_error(subscription, 'payment_error_card_expired', country)


def subscription_renewal_error(subscription, country=DEFAULT_COUNTRY):
    _subscription_renewal_error(subscription, 'payment_error_generic', country)


def login_succeeded(user, data):
    properties = {
        'country': data['country'],
        'ip': data['ip'],
        'device_family': data['device_family'],
        'os_family': data['os_family'],
        'user_agent_family': data['user_agent_family'],
        'url': data['url'],
    }

    logger.info('Segment login succeeded event for user_id: %s', user.pk)
    track(user.id, 'login_succeeded', properties=properties)


def user_frozen(user):
    flagged_reason = user.get_flagged_reason()
    data = {
        'user_first_name': user.first_name,
        'is_frozen': user.is_frozen,
        'flagged_reason': flagged_reason,
    }

    logger.info(
        'Segment user_frozen event for user_id: %s, is_frozen: %s flagged_reason: %s',
        user.pk,
        user.is_frozen,
        flagged_reason,
    )
    track(user.id, 'user_frozen', properties=data)


def subscription_payment_method_changed(subscription, client, ip):
    logger.info(
        'Segment payment_method_updated event for user_id: %s, subscription_id: %s',
        subscription.user_id,
        subscription.pk,
    )
    track(
        subscription.user_id,
        'payment_method_updated',
        properties={
            'user_first_name': subscription.user.first_name,
            'subscription_plan_name': subscription.plan.name,
        },
        context={'client': client, 'ip': ip},
    )


def subscription_canceled(subscription, client=None, ip=None):
    context = {}
    if client:
        context['client'] = client
    if ip:
        context['ip'] = ip
    logger.info(
        'Segment subscription_cancelled event for user_id: %s, subscription_id: %s',
        subscription.user_id,
        subscription.pk,
    )
    track(
        subscription.user_id,
        'subscription_cancelled',
        properties={
            'user_first_name': subscription.user.first_name,
            'subscription_plan_end_date': subscription.valid_until.isoformat(),
        },
        context=context,
    )


def subscription_changed(
    subscription, previous_plan, new_plan, client, ip, country=DEFAULT_COUNTRY
):
    card = new_plan.get_price_card(country=country)
    previous_card = previous_plan.get_price_card(country=country)
    data = {
        'current_subscription_plan_name': previous_plan.name,
        'current_subscription_plan_price': previous_card.currency_and_price,
        'date_when_new_plan_will_become_active': subscription.paid_until.isoformat(),
        'new_subscription_plan_name': new_plan.name,
        'new_subscription_plan_price': card.currency_and_price,
        'user_first_name': subscription.user.first_name,
        'product': {'name': new_plan.name, 'product_id': new_plan.id, 'quantity': 1},
        'revenue': str(card.price),
        'total': str(card.price),
    }
    logger.info(
        'Segment subscription_plan_changed_confirmation event for user_id: %s, subscription_id: %s',
        subscription.user_id,
        subscription.pk,
    )
    track(
        subscription.user_id,
        'subscription_plan_changed_confirmation',
        properties=data,
        context={'client': client, 'ip': ip},
    )


def subscription_tier_upgraded(
    subscription, previous_plan, client, ip, country=DEFAULT_COUNTRY
):
    """Special case of Subscription plan change, when User upgrades their subscription
    tier
    """
    previous_card = previous_plan.get_price_card(country=country)
    payment = subscription.latest_payment()
    data = {
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
    }
    logger.info(
        'Segment subscription_plan_changed_confirmation event for user_id: %s, subscription_id: %s',
        subscription.user_id,
        subscription.pk,
    )
    track(
        subscription.user_id,
        'subscription_plan_changed_confirmation',
        properties=data,
        context={'client': client, 'ip': ip},
    )


def subscription_new_intro_started(subscription, client, ip, country=DEFAULT_COUNTRY):
    _new_subscription_confirmation(
        subscription, 'Subscription IntroStarted', client, ip, country
    )


def subscription_new_started(subscription, client, ip, country=DEFAULT_COUNTRY):
    _new_subscription_confirmation(
        subscription, 'Subscription Started', client, ip, country
    )


def subscription_trial_started(subscription, client, ip, country_code):
    _new_subscription_confirmation(
        subscription, 'Subscription TrialStarted', client, ip, country_code
    )


def subscription_successful_renewal(subscription, amount, currency_code):
    logger.info(
        'Segment subscription_successful_renewal event for user_id: %s, subscription_id: %s',
        subscription.user_id,
        subscription.pk,
    )
    track(
        subscription.user_id,
        'subscription_successful_renewal',
        properties={
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


def split_accepted(split):
    logger.info(
        'Segment split_accepted event for user_id: %s, split_id: %s',
        split.user_id,
        split.pk,
    )
    track(
        split.user_id,
        'split_accepted',
        properties={
            'user_id': split.user_id,
            'split_rate': str(split.rate),
            'song_name': split.song.name,
        },
    )


def split_invites_expired(user_id, song_name):
    logger.info(
        f'Segment split_invites_expired event for user_id: {user_id}, song_name: {song_name}'
    )
    track(user_id, 'split_invites_expired', properties={'song_name': song_name})


def royalty_advance_notification(user_id, offer_type, amount):
    track(
        user_id,
        'ffwd_new_offer',
        properties={'amount': amount, 'type': offer_type, 'user_id': user_id},
    )


def _subscription_renewal_error(subscription, event, country):
    card = subscription.plan.get_price_card(country)
    data = {
        'user_first_name': subscription.user.first_name,
        'subscription_plan_name': subscription.plan.name,
        'subscription_plan_price': card.currency_and_price,
        'subscription_plan_grace_period': subscription.grace_period_until.isoformat(),
    }
    logger.info(
        'Segment %s event for user_id: %s, subscription_id: %s',
        event,
        subscription.user_id,
        subscription.pk,
    )
    track(subscription.user_id, event, properties=data)


def _new_subscription_confirmation(
    subscription, event, client, ip, country, **extra_data
):
    # card = subscription.plan.get_price_card(country=country)
    tier_name = tiers.get(subscription.plan.tier, subscription.plan.tier)
    payment = subscription.latest_payment()

    data = {
        'user_first_name': subscription.user.first_name,
        'subscription_plan_name': subscription.plan.name,
        'subscription_plan_price': f'{payment.currency.code} {str(payment.amount)}',
        'renewal_date': subscription.paid_until.isoformat(),
        'product': {
            'name': subscription.plan.name,
            'product_id': subscription.plan_id,
            'quantity': 1,
        },
        'revenue': str(payment.amount),
        'total': str(payment.amount),
        'tier': tier_name,
        'platform': payment.get_platform_display(),
    }
    if extra_data:
        data.update(extra_data)
    logger.info(
        'Segment %s event for user_id: %s, subscription_id: %s',
        event,
        subscription.user_id,
        subscription.pk,
    )
    track(
        subscription.user_id,
        event,
        properties=data,
        context={'client': client, 'ip': ip},
    )


def s4a_connected(user_id, artist_id):
    track(user_id, 's4a_complete', properties={'artist_id': artist_id})


def send_smart_link_release_email(user_id, smart_link):
    logger.info(
        f'Segment smart_link_release_email event for user_id: {user_id}, '
        f'smart_link: {smart_link}'
    )
    track(user_id, 'smart_link_release_email', properties={'url': smart_link})


def send_smart_link_delivered_email(
    user_id, link, include_pre_save_url, store_flags_dict
):
    data = {"url": link, "include_pre_save_url": include_pre_save_url}
    data.update(store_flags_dict)
    track(user_id, "smart_link_delivered_email", properties=data)


def signup_completed(user_id, platform_name, country, signup_path):
    logger.info(f'Segment Signup Completed event for user_id: {user_id}, ')
    data = {"platform": platform_name, "country": country, "signup_path": signup_path}
    track(user_id, "Signup Completed", properties=data)


def send_rb_successful(user_id, platform_name, country, event_data):
    logger.info(f'Segment Rb Successful event for user_id: {user_id} ')
    data = {"platform": platform_name, "country": country}
    data.update(event_data)
    track(user_id, "Rb Successful", properties=data)


def send_release_approved(event_data):
    user_id = event_data.pop('owner_id')
    logger.info(f'Segment Release Approved event for user_id: {user_id} ')
    track(user_id, "Release Approved", properties=event_data)


def send_release_not_approved(event_data):
    user_id = event_data.pop('owner_id')
    logger.info(f'Segment Release Not Approved event for user_id: {user_id} ')
    track(user_id, "Release Not Approved", properties=event_data)


def send_release_rejected(event_data):
    user_id = event_data.pop('owner_id')
    logger.info(f'Segment Release Rejected event for user_id: {user_id} ')
    track(user_id, "Release Rejected", properties=event_data)


def send_release_taken_down(event_data):
    user_id = event_data.pop('owner_id')
    logger.info(f'Segment Release Taken Down event for user_id: {user_id} ')
    track(user_id, "Release Taken Down", properties=event_data)


def send_release_deleted(event_data):
    user_id = event_data.pop('owner_id')
    logger.info(f'Segment Release Deleted event for user_id: {user_id} ')
    track(user_id, "Release Deleted", properties=event_data)


def send_release_released(event_data):
    user_id = event_data.pop('owner_id')
    logger.info(f'Segment Release Released event for user_id: {user_id} ')
    track(user_id, "Release Released", properties=event_data)


def send_release_delivered(event_data):
    user_id = event_data.pop('owner_id')
    logger.info(f'Segment Release Delivered event for user_id: {user_id} ')
    track(user_id, "Release Delivered", properties=event_data)


def send_release_undeliverable(event_data):
    user_id = event_data.pop('owner_id')
    logger.info(f'Segment Release Undeliverable event for user_id: {user_id} ')
    track(user_id, "Release Undeliverable", properties=event_data)


def user_requested_account_delete(user_id, data):
    logger.info(f'Segment Account Delete event for user_id: {user_id} ')
    payload = {
        "user_email": data.get('user_email'),
        "user_first_name": data.get('user_first_name'),
        "user_last_name": data.get('user_last_name'),
        "delete_requested_at": data.get('delete_requested_at'),
    }
    track(user_id, "Account Delete", properties=payload)


def identify_user(user, platform_name):
    if not user or user.id is None:
        return
    data = {
        'country_code': user.country,
        'created_at': datetime.now(),
        'email': user.email,
        'firstName': user.first_name,
        'lastName': user.last_name,
        'is_pro': user.is_pro,
        'newsletter': user.newsletter,
        'platform': platform_name,
        'tier': tiers.get(user.tier),
        'userId': user.id,
    }

    identify(user.id, data)


def track(user_id, event_name, properties=None, context=None):
    fn = track_async.delay if sample_is_active(WAFFLE_SAMPLE_KEY) else track_sync
    fn(user_id, event_name, properties, context)


def identify(user_id, data):
    fn = identify_async.delay if sample_is_active(WAFFLE_SAMPLE_KEY) else identify_sync
    fn(user_id, data)
