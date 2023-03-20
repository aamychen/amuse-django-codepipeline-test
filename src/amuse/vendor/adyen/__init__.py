import logging
from datetime import timedelta

import requests
from Adyen.settings import BASE_PAL_URL
from django.conf import settings
from django.utils import timezone


from amuse.analytics import (
    subscription_payment_method_expired,
    subscription_renewal_error,
    subscription_renewal_error_lack_of_funds,
)
from amuse.utils import CLIENT_ANDROID
from amuse.vendor.adyen.base import Adyen3DS, AdyenSubscription
from amuse.vendor.adyen.exceptions import (
    IssuerCountryAPIError,
    PaymentActionResponse,
    PaymentError,
    PaymentErrorResponse,
    PaymentRefusedResponse,
    PaymentUnknownResponse,
    PaymentPendingResponse,
)
from amuse.vendor.adyen.helpers import get_adyen_client
from countries.models import Country
from payments.models import PaymentTransaction
from subscriptions.models import Subscription


logger = logging.getLogger(__name__)


def get_payment_country(user_id, payment_details):
    """Check which country the CC is issued in, ref:
    https://docs.adyen.com/api-explorer/#/BinLookup/v50/getCostEstimate
    """
    base_url = BASE_PAL_URL.format(settings.ADYEN_PLATFORM)
    url = base_url + '/BinLookup/v50/getCostEstimate'
    country_lookup = {
        'amount': {'value': 0, 'currency': 'USD'},
        'encryptedCard': payment_details['paymentMethod']['encryptedCardNumber'],
        'merchantAccount': settings.ADYEN_MERCHANT_ACCOUNT,
        'shopperInteraction': 'Ecommerce',
        'shopperReference': str(user_id),
    }
    country_lookup_headers = {'x-api-key': settings.ADYEN_API_KEY}
    logger.info(
        'Adyen payment country lookup user %s, request: %s', user_id, country_lookup
    )

    response = requests.post(url, json=country_lookup, headers=country_lookup_headers)
    payload = response.json()
    logger.info('Adyen payment country lookup user %s, response: %s', user_id, payload)

    if response.status_code != 200:
        adyen_error_code = payload.get('errorCode')
        adyen_status_code = payload.get('status')
        is_payment_unsupported = adyen_status_code == 500 and adyen_error_code == '905'
        if is_payment_unsupported:
            logger.warning('Adyen payment details not supported: %s', payload)
        else:
            logger.info('Adyen payment country lookup fail: %s', payload)
        raise IssuerCountryAPIError(payload)

    country = payload['cardBin'].get('issuingCountry')
    if country in (None, 'unknown'):
        return None

    return Country.objects.filter(code=country).first()


def get_payment_methods(subscription_plan, country_code, client, localised=False):
    """Step 1 of Adyen flow.

    The user has selected a SubscriptionPlan and will then need to
    select payment method and enter payment details for the method.
    This request returns payment methods available to the user.
    """
    adyen = get_adyen_client()
    channel = 'Android' if client == CLIENT_ANDROID else 'Web'
    payload = {
        'merchantAccount': settings.ADYEN_MERCHANT_ACCOUNT,
        'countryCode': country_code,
        'channel': channel,
    }

    if localised:
        price_card = subscription_plan.get_price_card(country_code)
        payload['amount'] = {
            'value': price_card.price_adyen,
            'currency': price_card.currency.code,
        }
    else:
        payload['amount'] = {
            'value': subscription_plan.get_price_card().price_adyen,
            'currency': subscription_plan.get_price_card().currency.code,
        }

    response = adyen.checkout.payment_methods(payload).message
    payment_methods = response.get('paymentMethods', [])
    for i, payment_method in enumerate(payment_methods):
        if payment_method.get('name') == 'Card':
            response['paymentMethods'][i]['name'] = 'Credit Card'
            break
    return response


def create_subscription(
    user,
    subscription_plan,
    payment_details,
    country,
    client,
    ip,
    browser_info,
    force_3ds=False,
    return_url=None,
    localised=False,
    billing_address=None,
    custom_price=None,
    is_introductory_price=False,
):
    """Step 2 of Adyen flow.

    The user has selected a SubscriptionPlan and also given payment
    details as required by Adyen.

    These details need to be sent to Adyen (POST to /payments)
    """
    new_subscription = AdyenSubscription(
        user=user,
        subscription_plan=subscription_plan,
        payment_details=payment_details,
        country=country,
        client=client,
        ip=ip,
        browser_info=browser_info,
        force_3ds=force_3ds,
        return_url=return_url,
        localised=localised,
        billing_address=billing_address,
        custom_price=custom_price,
        is_introductory_price=is_introductory_price,
    )

    payment_func = lambda: new_subscription.create()

    try:
        response = _handle_payment(payment_func)
    except PaymentRefusedResponse as e:
        payment_func = lambda: new_subscription.create_3ds(e.payment)
        response = _handle_payment(payment_func)

    return response


def authorise_payment_method(
    user,
    payment_details,
    country,
    client,
    ip,
    browser_info,
    force_3ds=False,
    return_url=None,
    subscription_plan=None,
    localised=False,
    billing_address=None,
):
    """Authorise a card to be used for coming subscription fees."""
    subscription = user.current_subscription()
    if subscription_plan is None:
        subscription_plan = subscription.plan
    authorisation = AdyenSubscription(
        user=user,
        subscription_plan=subscription_plan,
        payment_details=payment_details,
        country=country,
        client=client,
        ip=ip,
        browser_info=browser_info,
        force_3ds=force_3ds,
        return_url=return_url,
        localised=localised,
        billing_address=billing_address,
    )
    payment_func = lambda: authorisation.authorise_payment_method()

    try:
        response = _handle_payment(payment_func)
    except PaymentRefusedResponse as e:
        payment_func = lambda: authorisation.authorise_payment_method_3ds(e.payment)
        response = _handle_payment(payment_func)
    return response


def renew_subscription(subscription, currency_code='USD'):
    existing_subscription = AdyenSubscription(subscription.user)

    if currency_code != 'USD':
        existing_subscription = AdyenSubscription(subscription.user, localised=True)

    try:
        existing_subscription.renew(subscription)
    except PaymentUnknownResponse as e:
        _disable_subscription(
            payment=e.payment, payment_status=e.status, error=e, use_grace_period=True
        )
        logger.exception(
            'PaymentUnknownResponse for PaymentTransaction:%s' % e.payment.pk
        )
        return {'is_success': False, 'error_message': e.message}
    except (PaymentErrorResponse, PaymentRefusedResponse) as e:
        # See: https://docs.adyen.com/development-resources/refusal-reasons
        refusal_reason = _get_refusal_reason(e.response)
        payment_source = e.response['additionalData'].get('fundingSource', '')

        is_expired_card = (
            refusal_reason == 'Expired Card'
            or e.payment.subscription.payment_method.is_expired()
        )
        is_fraud = 'fraud' in str(refusal_reason).lower()
        is_invalid_prepaid_card = payment_source == 'PREPAID' and refusal_reason in [
            'Invalid Card Number',
            'Not enough balance',
        ]
        if is_fraud:
            subscription.user.flag_for_fraud()
        if is_fraud or is_invalid_prepaid_card:
            _disable_subscription(
                payment=e.payment,
                payment_status=e.status,
                error=e,
                subscription_status=Subscription.STATUS_EXPIRED,
            )
            return {'is_success': False, 'error_message': e.message}

        _disable_subscription(
            payment=e.payment, payment_status=e.status, error=e, use_grace_period=True
        )
        if refusal_reason == 'Not enough balance':
            subscription_renewal_error_lack_of_funds(e.payment.subscription)
        elif is_expired_card:
            subscription_payment_method_expired(e.payment.subscription)
        else:
            subscription_renewal_error(e.payment.subscription)
        return {'is_success': False, 'error_message': e.message}
    except PaymentError as e:
        _disable_subscription(
            payment=e.payment, payment_status=e.status, error=e, use_grace_period=True
        )
        return {'is_success': False, 'error_message': e.message}
    except Exception as e:
        payment = subscription.latest_payment(allow_failed=True, allow_not_sent=True)
        _disable_subscription(
            payment=payment,
            payment_status=PaymentTransaction.STATUS_ERROR
            if payment.status == PaymentTransaction.STATUS_NOT_SENT
            else payment.status,
            error=e,
            use_grace_period=True,
        )
        logger.error(
            f'Uncaught exception occurred while renewing Subscription {subscription.pk}: {e}',
            exc_info=True,
        )
        return {'is_success': False, 'error_message': str(e)}

    return {'is_success': True}


def upgrade_subscription_tier(subscription, new_plan, custom_price):
    """
    Used for upgrading User's Subscription tier using existing payment information
    """
    try:
        existing_subscription = AdyenSubscription(
            user=subscription.user, custom_price=custom_price
        )
        payment_func = lambda: existing_subscription.upgrade_tier(
            subscription, new_plan
        )
        return _handle_payment(payment_func)
    except Exception as e:
        logger.error(
            f'Error occurred while upgrading Tier for Subscription {subscription.pk}: {e}',
            exc_info=True,
        )
        return {'is_success': False, 'error_message': str(e)}


def disable_recurring_payment(subscription):
    adyen = get_adyen_client()

    if not subscription.payment_method:
        logger.info(
            f"Unable to disable reoccurring subscription ({subscription.id}) for user ({subscription.user.id}) as no payment method was attached."
        )
        return

    payload = {
        "shopperReference": subscription.user.id,
        "recurringDetailReference": subscription.payment_method.external_recurring_id,
        "merchantAccount": settings.ADYEN_MERCHANT_ACCOUNT,
    }

    adyen.recurring.disable(payload)


def authorise_3ds(data, payment):
    payment_func = lambda: Adyen3DS().authorise_3ds(data, payment)
    return _handle_payment(payment_func)


def _update_payment(payment, payment_status=None, error=None):
    payment.external_payment_response = getattr(error, 'response', str(error))
    if not payment.external_transaction_id:
        payment.external_transaction_id = getattr(error, 'external_transaction_id', '')
    payment.status = payment_status
    payment.save()


def _disable_subscription(
    payment,
    payment_status=None,
    error=None,
    use_grace_period=False,
    subscription_status=None,
):
    today = timezone.now().date()
    subscription = payment.subscription

    if use_grace_period:
        grace_period_until = subscription.allowed_grace_period_until()
        subscription.grace_period_until = grace_period_until
        if grace_period_until <= today:
            subscription.status = Subscription.STATUS_EXPIRED
        else:
            subscription.status = Subscription.STATUS_GRACE_PERIOD

    if subscription_status:
        subscription.status = subscription_status
    subscription.valid_until = subscription.paid_until
    subscription.save()

    _update_payment(payment, payment_status, error)
    logger.info(
        'Disabled subscription %s. Subscription status: %s. Related PaymentTransaction: %s'
        % (
            payment.subscription_id,
            payment.subscription.get_status_display(),
            payment.pk,
        )
    )


def _handle_payment(payment_func):
    try:
        payment_func()
    except PaymentRefusedResponse as e:
        reason = _get_refusal_reason(e.response)
        if reason == '3D Secure Mandated':
            raise e

        is_fraud = 'fraud' in str(reason).lower()
        if is_fraud:
            e.payment.user.flag_for_fraud()
            _disable_subscription(
                e.payment, e.status, e, subscription_status=Subscription.STATUS_ERROR
            )
        else:
            _handle_subscription_error(e)
        return {'is_success': False, 'error_message': e.message}
    except (PaymentActionResponse, PaymentPendingResponse) as e:
        if 'action' in e.response:
            return {
                'is_success': False,
                'action': e.response['action'],
                'transaction_id': e.payment.pk,
            }
        else:
            _handle_subscription_error(e)
            return {'is_success': False, 'error_message': e.message}
    except PaymentUnknownResponse as e:
        _disable_subscription(
            e.payment, e.status, e, subscription_status=Subscription.STATUS_ERROR
        )
        raise e
    except PaymentError as e:
        _handle_subscription_error(e)
        return {'is_success': False, 'error_message': e.message}

    return {'is_success': True}


def _handle_subscription_error(error):
    # if Subscription status is ACTIVE this is a failed attempt at updating the
    # PaymentMethod - do NOT disable the Subscription
    subscription = error.payment.subscription
    if subscription.status == Subscription.STATUS_ACTIVE:
        _update_payment(error.payment, error.status, error)
    else:
        _disable_subscription(
            error.payment,
            error.status,
            error,
            subscription_status=Subscription.STATUS_ERROR,
        )


def _get_refusal_reason(response):
    try:
        reason = response['additionalData'].get('inferredRefusalReason')
        if not reason:
            reason = response.get('refusalReason')
        return reason
    except (KeyError, ValueError, IndexError):
        logger.info(f'Unable to get refusal reason from response: {response}')
        return None
