from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_exempt

from amuse.analytics import email_verified
from amuse.tokens import (
    email_verification_token_generator,
    withdrawal_verification_token_generator,
)
from users.models import User, Transaction


@csrf_exempt
def email_verification_confirm(request, uidb64=None, token=None):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and email_verification_token_generator.check_token(user, token):
        user.email_verified = True
        user.save()

        email_verified(user.id)
        return HttpResponseRedirect(reverse('email_verification_done'))
    else:
        return HttpResponseRedirect(reverse('email_verification_fail'))


def email_verification_done(request):
    return render(
        request, template_name='website/registration/email_verification_done.html'
    )


def email_verification_fail(request):
    return render(
        request, template_name='website/registration/email_verification_fail.html'
    )


def withdrawal_verification_confirm(request, uidb64=None, token=None):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        transaction = Transaction.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Transaction.DoesNotExist):
        transaction = None

    if transaction is not None and withdrawal_verification_token_generator.check_token(
        transaction, token
    ):
        transaction.withdrawal.verified = True
        transaction.withdrawal.save()
        template_name = 'website/withdrawal_verification_done.html'
    else:
        template_name = 'website/withdrawal_verification_fail.html'

    return render(request, template_name=template_name)
