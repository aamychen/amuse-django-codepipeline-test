from amuse.settings.constants import NONLOCALIZED_PAYMENTS_COUNTRY as DEFAULT_COUNTRY
from amuse.vendor.appsflyer import events as af
from amuse.vendor.impact import Impact
from amuse.vendor.segment import events as segment
from countries.models import Country
from users.models import AppsflyerDevice, User
from .platform import PlatformType, PlatformHelper


def email_verified(user_id):
    segment.email_verified(user_id)

    device = get_device(user_id)
    af.email_verified(device, user_id)


def get_device(user_id):
    if user_id is None:
        return None

    return AppsflyerDevice.objects.filter(user_id=user_id).order_by('-updated').first()


def ffwd_started(user, withdrawal_amount):
    segment.ffwd_started(user.id, withdrawal_amount)

    device = get_device(user.id)
    af.ffwd_started(device, user, withdrawal_amount)


def login_succeeded(user, data):
    segment.login_succeeded(user, data)

    device = get_device(user.id)
    af.login_succeeded(device, user, data)


def music_upload(user: User, platform: PlatformType):
    device = get_device(user.id)

    Impact(user.id, user.email, platform).music_upload()


def royalty_advance_notification(user_id, offer_type, amount):
    segment.royalty_advance_notification(user_id, offer_type, amount)

    device = get_device(user_id)
    af.royalty_advance_notification(device, user_id, offer_type, amount)


def sign_up(user: User, platform: PlatformType, click_id: str):
    device = get_device(user.id)

    Impact(user.id, user.email, platform).sign_up(click_id)


def split_accepted(split):
    segment.split_accepted(split)

    device = get_device(split.user_id)
    af.split_accepted(device, split)


def split_invites_expired(user_id, song_name):
    segment.split_invites_expired(user_id, song_name)

    device = get_device(user_id)
    af.split_invites_expired(device, user_id, song_name)


def subscription_canceled(subscription, client=None, ip=None):
    segment.subscription_canceled(subscription, client=client, ip=ip)

    device = get_device(subscription.user_id)
    af.subscription_canceled(device, subscription, ip=ip)


def subscription_changed(
    subscription, previous_plan, new_plan, client, ip, country=DEFAULT_COUNTRY
):
    segment.subscription_changed(
        subscription, previous_plan, new_plan, client, ip, country=country
    )

    device = get_device(subscription.user_id)
    af.subscription_changed(
        device, subscription, previous_plan, new_plan, ip, country=country
    )


def subscription_tier_upgraded(
    subscription, previous_plan, client, ip, country=DEFAULT_COUNTRY
):
    """Special case of Subscription plan change, when User upgrades their subscription
    tier
    """
    segment.subscription_tier_upgraded(
        subscription, previous_plan, client, ip, country=country
    )

    device = get_device(subscription.user_id)
    af.subscription_tier_upgraded(
        device, subscription, previous_plan, ip, country=country
    )


def subscription_new_intro_started(
    subscription, platform: PlatformType, client, ip, country=DEFAULT_COUNTRY
):
    user = subscription.user
    segment.subscription_new_intro_started(subscription, client, ip, country)

    device = get_device(user.id)
    af.subscription_new_intro_started(device, subscription, ip, country=country)

    # For IMPACT there is no intro_started event.
    Impact(user.id, user.email, platform).subscription_new_started(
        subscription, country
    )


def subscription_new_started(
    subscription, platform: PlatformType, client, ip, country=DEFAULT_COUNTRY
):
    user = subscription.user
    segment.subscription_new_started(subscription, client, ip, country)

    device = get_device(user.id)
    af.subscription_new_started(device, subscription, ip, country=country)

    Impact(user.id, user.email, platform).subscription_new_started(
        subscription, country
    )


def subscription_payment_method_changed(subscription, client, ip):
    segment.subscription_payment_method_changed(subscription, client, ip)

    device = get_device(subscription.user_id)
    af.subscription_payment_method_changed(device, subscription, ip)


def subscription_payment_method_expired(subscription, country=DEFAULT_COUNTRY):
    segment.subscription_payment_method_expired(subscription, country)

    device = get_device(subscription.user_id)
    af.subscription_payment_method_expired(device, subscription, country)


def subscription_renewal_error(subscription, country=DEFAULT_COUNTRY):
    segment.subscription_renewal_error(subscription, country)

    device = get_device(subscription.user_id)
    af.subscription_renewal_error(device, subscription, country)


def subscription_renewal_error_lack_of_funds(subscription, country=DEFAULT_COUNTRY):
    segment.subscription_renewal_error_lack_of_funds(subscription, country)

    device = get_device(subscription.user_id)
    af.subscription_renewal_error_lack_of_funds(device, subscription, country)


def subscription_successful_renewal(subscription, amount, currency_code):
    segment.subscription_successful_renewal(subscription, amount, currency_code)

    device = get_device(subscription.user_id)
    af.subscription_successful_renewal(device, subscription, amount, currency_code)


def subscription_trial_started(
    subscription, platform: PlatformType, client, ip, country_code
):
    user = subscription.user
    segment.subscription_trial_started(subscription, client, ip, country_code)

    device = get_device(user.id)
    af.subscription_trial_started(device, subscription, ip, country=country_code)


def update_is_pro_state(user):
    segment.update_is_pro_state(user)


def user_frozen(user):
    segment.user_frozen(user)


def s4a_connected(user_id, artist_id):
    segment.s4a_connected(user_id, artist_id)

    device = get_device(user_id)
    af.s4a_connected(device, user_id, artist_id)


def signup_completed(user, platform_name, detected_country_name, signup_path):
    segment.identify_user(user, platform_name)
    segment.signup_completed(user.id, platform_name, detected_country_name, signup_path)

    device = get_device(user.id)
    af.signup_completed(
        device, user.id, platform_name, detected_country_name, signup_path
    )


def rb_successful(user_id, request, event_data):
    if not _should_trigger_segment_event(request):
        return
    detected_country_name = _get_country_name(request)
    platform_name = PlatformHelper.from_request(request).name
    segment.send_rb_successful(
        user_id, platform_name, detected_country_name, event_data
    )

    device = get_device(user_id)
    af.rb_successful(device, user_id, platform_name, detected_country_name, event_data)


def segment_release_approved(release):
    segment.send_release_approved(create_event_data(release))


def segment_release_not_approved(release):
    segment.send_release_not_approved(create_event_data(release))


def segment_release_rejected(release):
    segment.send_release_rejected(create_event_data(release))


def segment_release_taken_down(release):
    segment.send_release_taken_down(create_event_data(release))


def segment_release_deleted(release):
    segment.send_release_deleted(create_event_data(release))


def segment_release_released(release):
    segment.send_release_released(create_event_data(release))


def segment_release_delivered(release):
    segment.send_release_delivered(create_event_data(release))


def segment_release_undeliverable(release):
    segment.send_release_undeliverable(create_event_data(release))


def user_requested_account_delete(user_id: int, data: dict):
    segment.user_requested_account_delete(user_id, data)


def _get_country_name(request):
    detected_country_name = None
    detected_country_code = request.META.get('HTTP_CF_IPCOUNTRY')
    detected_country = Country.objects.filter(code=detected_country_code).first()
    if detected_country is not None:
        detected_country_name = detected_country.name
    return detected_country_name


def _should_trigger_segment_event(request):
    """HTTP_X_TRIGGER_EVENT - Custom request header which suggest does segment event
    need to be triggered on BE side or not so we don't trigger it twice - on frontend and backend
    ie. to avoid duplicates"""
    if not request:
        return
    return request.META.get('HTTP_X_TRIGGER_EVENT') == '1'


def create_event_data(release):
    release_flags = [
        flag_reason for (flag_reason, is_flagged) in release.error_flags if is_flagged
    ]

    songs_with_flags = []
    # For every song in that release
    for song in release.songs.all():
        # If it has error flag/flags
        error_flags = []
        # Collect the error flags description where the flag is valid into a list
        for flag in song.error_flags:
            (flag_reason, is_flagged) = flag
            if is_flagged:
                error_flags.append(flag_reason)

        if error_flags:
            songs_with_flags.append(
                {"song_id": song.pk, "song_name": song.name, "error_flags": error_flags}
            )

    return {
        "owner_id": release.user.id,
        "release_id": release.id,
        "release_name": release.name,
        "release_status": release.status,
        "main_primary_artist": release.main_primary_artist.name
        if release.main_primary_artist
        else "",
        "release_date": release.release_date,
        "release_flags": release_flags,
        "songs_with_flags": songs_with_flags,
        "schedule_type": release.SCHEDULE_TYPES_MAP[release.schedule_type],
    }
