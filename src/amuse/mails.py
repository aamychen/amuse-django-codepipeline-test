from django.core.mail import EmailMessage
from django.urls import reverse, get_resolver
from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from djrill.exceptions import DjrillError, MandrillRecipientsRefused

from amuse.logging import logger
from amuse.tokens import (
    email_verification_token_generator,
    password_reset_token_generator,
    withdrawal_verification_token_generator,
)

#  Map of template suffix => country codes.
LOCALIZED_TEMPLATES = {
    'ES': {
        'XX',  # XX used as fake country code while testing templates.
        'MX',  # Mexico
        'CO',  # Colombia
        'ES',  # Spain
        'AR',  # Argentina
        'PE',  # Peru
        'VE',  # Venezuela
        'CL',  # Chile
        'EC',  # Ecuador
        'GT',  # Guatemala
        'CU',  # Cuba
        'BO',  # Bolivia
        'DO',  # Dominican Republic
        'HN',  # Honduras
        'PY',  # Paraguay
        'SV',  # El Salvador
        'NI',  # Nicaragua
        'CR',  # Costa Rica
        'PR',  # Puerto Rico
        'PA',  # Panama
        'UY',  # Uruguay
    }
}

RELEASE_TEMPLATES = [
    "SUBMISSION_APPROVED",
    "SUBMISSION_RECEIVED",
    "SUBMISSION_UPLOAD_FAILURE",
    "RELEASE_LINK",
]


def resolve_lang(country):
    for lang, countries in LOCALIZED_TEMPLATES.items():
        if country in countries:
            return lang


def create_localized_template_name(template_name, country):
    suffix = resolve_lang(country)
    return f'{template_name}_{suffix}' if suffix else template_name


def send_base_template(from_email, to_user, subject, content, bcc=[]):
    msg = EmailMessage(to=[to_user.email])
    msg.template_name = create_localized_template_name('BASE', to_user.country)
    msg.subject = subject
    msg.from_email = from_email
    msg.bcc = bcc

    msg.global_merge_vars = {'FNAME': to_user.first_name, 'MAIL_CONTENT': content}

    msg.send()


def send_password_reset(user, urlconf=None):
    template_name = create_localized_template_name('PASSWORD_RESET', user.country)

    url = '%s%s' % (
        settings.APP_URL.rstrip('/'),
        reverse(
            'password_reset_confirm',
            kwargs={
                'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': password_reset_token_generator.make_token(user),
            },
            urlconf=urlconf,
        ),
    )
    context = {user.email: {'URL': url}}

    send_template_mail(template_name, user.email, context)


def send_email_verification(user):
    template_name = create_localized_template_name('EMAIL_VERIFICATION', user.country)

    url = '%s%s' % (
        settings.APP_URL.rstrip('/'),
        reverse(
            'email_verification_confirm',
            kwargs={
                'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': email_verification_token_generator.make_token(user),
            },
        ),
    )
    context = {user.email: {'URL': url}}

    send_template_mail(template_name, user.email, context)


def send_withdrawal_failure(user_id, error_message):
    from users.models import User

    user = User.objects.get(pk=user_id)
    template_name = create_localized_template_name('WITHDRAWAL_FAILURE', user.country)

    context = {user.email: {'ERROR_MESSAGE': error_message}}
    send_template_mail(template_name, user.email, context)


def send_release_pending(release):
    template = 'SUBMISSION_RECEIVED'
    context_keys = ['FNAME', 'RELEASE_NAME', 'RELEASE_ID']
    send_release_template_mail(template, release, context_keys)


def send_release_delivered(release):
    template = 'SUBMISSION_APPROVED'
    context_keys = [
        'FNAME',
        'ARTIST_NAME',
        'RELEASE_NAME',
        'RELEASE_DATE',
        'RELEASE_ID',
        'UPC_CODE',
    ]

    if release.cover_art.file and release.cover_art.file.name:
        context_keys.append('COVER_ART_URL')

    send_release_template_mail(template, release, context_keys)


def send_release_upload_failure(release):
    template = 'SUBMISSION_UPLOAD_FAILURE'
    context_keys = ['FNAME', 'RELEASE_NAME', 'RELEASE_ID']

    try:
        send_release_template_mail(template, release, context_keys)
    except DjrillError as err:
        logger.error(err)


def send_release_link(release):
    template = 'RELEASE_LINK'
    context_keys = ['LINK', 'FIRST_NAME', 'RELEASE_NAME', 'RELEASE_ID']
    send_release_template_mail(template, release, context_keys)


def send_security_update_mail(user):
    template_name = create_localized_template_name('SECURITY_UPDATES', user.country)
    send_template_mail(template_name, user.email, {})


def send_template_mail(template_name, email, context):
    msg = EmailMessage(to=[email])
    msg.use_template_from = True
    msg.use_template_subject = True
    msg.template_name = template_name
    msg.merge_vars = context
    try:
        msg.send()
    except MandrillRecipientsRefused as e:
        logger.info(e)


def build_release_context(user, release, keys):
    artist_name = user.artist_name  # fallback
    if release.main_primary_artist:
        artist_name = release.main_primary_artist.name

    base_context = {
        'ARTIST_NAME': artist_name,
        'FIRST_NAME': user.first_name,
        'FNAME': user.first_name,
        'LINK': release.link,
        'RELEASE_DATE': release.release_date.strftime("%d, %b %Y")
        if release.release_date
        else None,
        'RELEASE_ID': release.id,
        'RELEASE_NAME': release.name,
        'UPC_CODE': release.upc_code,
    }

    if "COVER_ART_URL" in keys:
        base_context["COVER_ART_URL"] = release.cover_art.file.url_400x400

    return {user.email: {key: base_context.get(key) for key in keys}}


def send_release_template_mail(template, release, context_keys):
    assert template in RELEASE_TEMPLATES

    owner = release.user
    creator = release.created_by

    if creator and owner != creator:
        template_name = create_localized_template_name(template, creator.country)
        context = build_release_context(creator, release, context_keys)
        send_template_mail(template_name, creator.email, context)

    template_name = create_localized_template_name(template, owner.country)
    context = build_release_context(owner, release, context_keys)
    send_template_mail(template_name, owner.email, context)
