from logging import getLogger
from django.conf import settings
from mailchimp_transactional import Client
from djrill.exceptions import MandrillRecipientsRefused
from releases.models import Song
from amuse.mails import resolve_lang, send_base_template, create_localized_template_name


logger = getLogger(__name__)


'''
Map of languge codes => language labels.

This is legacy because there is multiple ways to
send emails. One relies on the Mandrill name and
one depends on the labels (tags).

The `resolve_lang` function finds out what language
the user is considered to have based on country. This
map then resolves what language label that language
corresponds to.

A way to reduce this complexity is to store
the language code immediately on the user in the DB.

'''
COUNTRY_LANG_LABEL_MAP = {'ES': 'lang-es'}


def resolve_lang_label(country):
    lang = resolve_lang(country)
    if lang in COUNTRY_LANG_LABEL_MAP:
        return COUNTRY_LANG_LABEL_MAP[lang]
    return 'lang-en'


def create_resolver(country):
    templates = get_templates('tollgate', country)

    def find_template(label):
        for template in templates:
            if label in template['labels']:
                return template

    return find_template


def get_tollgate_templates():
    client = Client(settings.MANDRILL_API_KEY)
    return client.templates.list(body={"label": "tollgate"})


def get_template_by_name(name):
    client = Client(settings.MANDRILL_API_KEY)
    return client.templates.info(body={"name": name})


def get_templates(label, country):
    lang_label = resolve_lang_label(country)

    all = get_tollgate_templates()
    templates = []

    for t in all:
        if label in t['labels'] and lang_label in t['labels']:
            templates.append(t)

    return templates


def get_templates_for_release(release):
    country = release.user.country

    song_template_name = create_localized_template_name('SONG-NAME', country)

    resolve_template = create_resolver(country)
    templates = []

    if release.error_flags > 0:
        for k, v in release.error_flags.items():
            t = resolve_template(k)

            if t and v == True:
                templates.append(t)

            if not t:
                logger.error("Template missing for: %s" % (k))

    for s in release.songs.all():
        if s.error_flags > 0:
            song_template = get_template_by_name(song_template_name)
            new_code = song_template['code'].replace('*|SONG_NAME|*', s.name)
            song_template['code'] = new_code
            templates.append(song_template)

            for k, v in s.error_flags.items():
                t = resolve_template(k)
                if t and v == True:
                    templates.append(t)

                if not t:
                    logger.error("Template missing for: %s" % (k))

    return templates


def has_flags(release):
    if release.error_flags > 0:
        return True

    for s in release.songs.all():
        if s.error_flags > 0:
            return True

    return False


def has_not_approved_flags(release):
    manual_explanation_flags_release = {
        'explicit_parental-advisory',
        'release_date-changed',
    }
    manual_explanation_flags_song = {'explicit_lyrics'}

    # Check release
    set_flags = {flag for flag, active in release.error_flags.items() if active}

    if set_flags - manual_explanation_flags_release:
        return True

    # Check songs
    for song in release.songs.all():
        set_flags = {flag for flag, active in song.error_flags.items() if active}
        if set_flags - manual_explanation_flags_song:
            return True

    return False


def send_mail(user, subject, html, from_mail=None):
    try:
        if not from_mail:
            from_mail = 'support@amuse.io'

        send_base_template(from_mail, user, subject, html)
    except MandrillRecipientsRefused as mrr:
        logger.warning(mrr)
        raise


def send_template(name, release, default_subject):
    intro_template = get_template_by_name(name)
    new_code = intro_template['code'].replace('*|RELEASE_NAME|*', release.name)
    intro_template['code'] = new_code
    templates = get_templates_for_release(release)
    from_email = intro_template['from_email']
    subject = intro_template['subject']

    if not subject:
        subject = default_subject

    html = intro_template['code']
    html += render_templates(templates)
    html += render_release_id(release)
    release_owner = release.user
    release_creator = release.created_by

    if release_creator and release_owner != release_creator:
        send_mail(release_creator, subject, html, from_email)

    send_mail(release_owner, subject, html, from_email)


def send_approved_mail(release):
    if has_flags(release):
        intro_name = create_localized_template_name(
            'INTRO_APPROVED', release.user.country
        )
        subject = 'Your release has been approved'

        send_template(intro_name, release, subject)


def send_not_approved_mail(release):
    if has_not_approved_flags(release):
        intro_name = create_localized_template_name(
            'INTRO_PENDING', release.user.country
        )
        subject = 'Your release is pending'

        send_template(intro_name, release, subject)


def send_rejected_mail(release):
    if has_flags(release):
        intro_name = create_localized_template_name(
            'INTRO_REJECTED', release.user.country
        )
        subject = 'Your release has been rejected'

        send_template(intro_name, release, subject)


def render_templates(templates):
    html = ""

    for t in templates:
        html += t['code']
        html += "<br>"

    return html


def render_release_id(release):
    return '<p style="font-size: 10px; color: gray;">Ref: %s</p>' % release.id
