import base64
import binascii
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.signing import BadSignature, TimestampSigner
from django.http import Http404, HttpResponseRedirect
from django.template.loader import get_template
from django.template.response import HttpResponse, TemplateResponse
from django.urls import reverse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

from amuse.analytics import subscription_new_intro_started, subscription_new_started
from amuse.tokens import payment_success_token_generator
from amuse.utils import get_ip_address, is_authenticated_http
from amuse.vendor.adyen import authorise_3ds
from amuse.platform import PlatformHelper
from payments.models import PaymentTransaction
from subscriptions.models import SubscriptionPlan, Subscription
from users.models import User
from payments.notifications.adyen import AdyenNoificationsHandler


logger = logging.getLogger(__name__)


@staff_member_required
def adyen_debug(request):
    return TemplateResponse(
        request,
        'adyen_debug.html',
        {
            'origin_key': settings.ADYEN_ORIGIN_KEY,
            'subscription_plan_id': SubscriptionPlan.objects.first().pk,
            'user_token': str(request.user.auth_token),
        },
    )


@csrf_exempt
def adyen_3ds(request, payment_id, encrypted_user_id):
    if request.method == 'GET':
        request_data = request.GET
    elif request.method == 'POST':
        request_data = request.POST
    else:
        logger.info('Adyen 3DS bad method')
        raise Http404()

    logger.info(f'Received 3DS Adyen request (data={request_data}')

    try:
        decrypted_user_id = TimestampSigner().unsign(encrypted_user_id)
    except BadSignature as e:
        logger.info(
            f'Adyen 3DS bad signature {e} (encrypted signature was {encrypted_user_id}'
        )
        raise Http404()

    try:
        user = User.objects.get(pk=decrypted_user_id)
    except User.DoesNotExist:
        logger.info(f'Adyen 3DS no user with pk={decrypted_user_id}')
        raise Http404()

    try:
        payment = PaymentTransaction.objects.get(pk=payment_id, user=user)
    except PaymentTransaction.DoesNotExist:
        logger.info(
            f'Adyen 3DS no payment transaction with pk={payment_id} and user={user.pk}'
        )
        raise Http404()

    if payment.status != PaymentTransaction.STATUS_NOT_SENT:
        logger.info(f'Adyen 3DS payment transaction already sent pk={payment_id}')
        raise Http404()

    authorise_3ds(request_data, payment)

    # replace WRB_URL with localhost:3000 for local testing
    # using payment.id, since web doesn't see payment.external_transaction_id
    # at this point in checkout, it's masked by adyen in paymentData object
    redirect_result = (
        payment.status
        in (PaymentTransaction.STATUS_DECLINED, PaymentTransaction.STATUS_ERROR)
        and 'false'
        or 'true'
    )

    _send_subscription_new_started_event(request, payment)

    # webapp needs to know which flow is used
    # new subscription = 'checkout'
    # update payment method = 'auth'
    flow = payment.amount == 0 and 'auth' or 'checkout'

    webapp_return_url = (
        settings.WRB_URL
        + settings.ADYEN_3DS_WEBAPP_RETURN_PATH
        + redirect_result
        + '&transactionid='
        + payment_success_token_generator.make_token({'transaction_id': payment.id})
        + f'&flow={flow}'
    )
    return HttpResponseRedirect(webapp_return_url)


def _send_subscription_new_started_event(request, payment):
    try:
        if payment.status != PaymentTransaction.STATUS_APPROVED:
            return

        if payment.amount == 0:
            return

        if payment.subscription.status != Subscription.STATUS_ACTIVE:
            return

        country_code = payment.country.code

        ip = get_ip_address(request)
        client = request.META.get('HTTP_USER_AGENT', '')
        subscription_started = (
            subscription_new_intro_started
            if payment.is_introductory
            else subscription_new_started
        )
        subscription_started(
            payment.subscription,
            PlatformHelper.from_payment(payment),
            client,
            ip,
            country_code,
        )
    except Exception as e:
        logger.error(f'"Subscription Started" Error: {e}')


class AdyenNotificationView(View):
    def post(self, request):
        logger.info(f'Adyen Notification webhook: {request.body}')
        if not is_authenticated_http(
            request,
            settings.ADYEN_NOTIFICATION_USER,
            settings.ADYEN_NOTIFICATION_PASSWORD,
        ):
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)

        data = json.loads(request.body)

        if not self._is_valid_payload_hmac(data):
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)

        is_done = AdyenNoificationsHandler().process_notification(data)
        if not is_done:
            logger.warning(
                f'AdyenNoificationsHandler failed to process notification {data}'
            )
        return HttpResponse('[accepted]', status=status.HTTP_200_OK)

    def _is_valid_payload_hmac(self, data):
        if settings.ADYEN_NOTIFICATION_HMAC:
            for item_data in data['notificationItems']:
                item = item_data['NotificationRequestItem']
                if not self._is_valid_item_hmac(item):
                    logger.warning(
                        f'Adyen endpoint received invalid HMAC signature for item {item}'
                    )
                    return False
        return True

    def _is_valid_item_hmac(self, item):
        """Needed because Adyen 2.2.0 utils.is_valid_hmac is broken, see:
        https://docs.adyen.com/development-resources/notifications/verify-hmac-signatures#verify-using-your-own-solution
        https://github.com/Adyen/adyen-python-api-library/issues/96
        """
        if 'additionalData' in item and item['additionalData'].get('hmacSignature'):
            escaped_reference = (
                item.get('originalReference', '')
                .replace('\\', '\\\\')
                .replace(':', '\\:')
            )
            sign_parts = [
                item['pspReference'],
                escaped_reference,
                item['merchantAccountCode'],
                item['merchantReference'],
                str(item['amount']['value']),
                item['amount']['currency'],
                item['eventCode'],
                item['success'],
            ]
            string_to_sign = ':'.join(sign_parts)

            hmac_key = binascii.a2b_hex(settings.ADYEN_NOTIFICATION_HMAC)
            signed = hmac.new(hmac_key, string_to_sign.encode('utf-8'), hashlib.sha256)
            signed_string = base64.b64encode(signed.digest()).decode("utf-8")
            expected_signature = item['additionalData']['hmacSignature']

            return signed_string == expected_signature
        return True

    def _is_valid_merchant_account(self, data):
        for item_data in data['notificationItems']:
            item = item_data['NotificationRequestItem']
            merchant_account = item['merchantAccountCode']
            if merchant_account != settings.ADYEN_MERCHANT_ACCOUNT:
                logger.warning(
                    'Adyen Merchant Account mismatch, '
                    f'received: {merchant_account}, '
                    f'configured for: {settings.ADYEN_MERCHANT_ACCOUNT}'
                )
                return False
        return True

    def _get_zendesk_payload(self, user, data):
        base_url = settings.ADMIN_URL.rstrip('/')
        user_admin_url = base_url + reverse('admin:users_user_change', args=(user.pk,))
        context = {
            'adyen_data': data,
            'code': data['eventCode'],
            'payment': None,
            'reason': data.get('reason', None),
            'received_time': data.get('eventDate'),
            'subscription': None,
            'user': user,
            'user_admin_url': user_admin_url,
        }

        external_transaction_id = data.get('originalReference', None)
        if external_transaction_id:
            payment = PaymentTransaction.objects.filter(
                external_transaction_id=external_transaction_id
            ).first()
            if payment:
                context['payment'] = payment
                context['payment_admin_url'] = base_url + reverse(
                    'admin:payments_paymenttransaction_change', args=(payment.pk,)
                )
                subscription = payment.subscription
                context['subscription'] = subscription
                context['subscription_admin_url'] = base_url + reverse(
                    'admin:subscriptions_subscription_change', args=(subscription.pk,)
                )
                context[
                    'subscription_payments_count'
                ] = subscription.paymenttransaction_set.filter(
                    status=PaymentTransaction.STATUS_APPROVED
                ).count()

        template = get_template('adyen_zendesk_notification_ticket.html')
        return {
            'subject': 'Adyen Payment Notification',
            'comment': template.render(context),
        }


adyen_notification_view = csrf_exempt(AdyenNotificationView.as_view())


# def generate_hpp_sig(item, hmac_key):
