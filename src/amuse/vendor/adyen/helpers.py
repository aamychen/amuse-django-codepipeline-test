from datetime import datetime, timezone, date

import Adyen
from dateutil.relativedelta import relativedelta
from django.conf import settings

from payments.models import PaymentMethod
from amuse.logging import logger


def get_adyen_client():
    kwargs = {
        'app_name': 'Amuse.io',
        'platform': settings.ADYEN_PLATFORM,
        'xapikey': settings.ADYEN_API_KEY,
    }

    if settings.ADYEN_PLATFORM == 'live':
        kwargs['live_endpoint_prefix'] = settings.ADYEN_LIVE_ENDPOINT_PREFIX
    return Adyen.Adyen(**kwargs)


def convert_to_end_of_the_day(date):
    return datetime(
        date.year,
        date.month,
        date.day,
        23,
        59,
        59,
        tzinfo=timezone.utc,
    )


def get_or_create_payment_method(user, response):
    payment_data = response.get('additionalData')

    kwargs = {
        'user': user,
        'expiry_date': None,
        'method': None,
        'summary': None,
    }

    if payment_data:
        if 'expiryDate' in payment_data:
            try:
                expiry_date = payment_data['expiryDate']
                month, year = expiry_date.split('/')
                expiry_date = date(int(year), int(month), 1) + relativedelta(
                    months=1, days=-1
                )
                kwargs['expiry_date'] = expiry_date
            except Exception as e:
                logger.error(f'Error processing expiryDate={expiry_date} reason={e}')

        # Adyen returns payment method in 'additionalData'.'paymentMethod' for cards
        # and just in 'paymentMethod' for paypal (and other payment methods I assume)
        if 'paymentMethod' in payment_data:
            kwargs['method'] = payment_data['paymentMethod']

        if 'cardSummary' in payment_data:
            kwargs['summary'] = payment_data['cardSummary']

        # Adyen does not send recurring.recurringDetailReference for renewal requests
        if 'recurring.recurringDetailReference' in payment_data:
            kwargs['external_recurring_id'] = payment_data[
                'recurring.recurringDetailReference'
            ]

    # Adyen returns payment method in 'additionalData'.'paymentMethod' for cards
    # and just in 'paymentMethod' for paypal (and other payment methods I assume)
    if 'paymentMethod' in response:
        kwargs['method'] = response['paymentMethod']

    # we shouldn't have multiple PaymentMethods returned but there are a couple
    # of Users with "bad" data so we'll be safe here
    method = PaymentMethod.objects.filter(**kwargs).first()
    if not method:
        method = PaymentMethod.objects.create(**kwargs)
    return method
