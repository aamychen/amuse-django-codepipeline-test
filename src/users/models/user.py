import pyotp
from django.conf import settings
from django.contrib.auth.hashers import (
    check_password,
    is_password_usable,
    make_password,
)
from django.db import models
from django.dispatch import receiver
from django.utils import timezone
from django.utils.functional import cached_property
from googleplaces import GooglePlacesError
from rest_framework.authtoken.models import Token
from datetime import datetime

from amuse import mails
from amuse.db.decorators import field_observer, observable_fields
from amuse.logging import logger
from amuse.vendor.segment.events import user_frozen
from users.managers import OtpDeviceManager, UserManager
from users.models import UserArtistRole
from .transaction import ZERO


@observable_fields(exclude=('updated'))
class User(models.Model):
    TIER_FREE = 0  # Constant for free tier users

    CATEGORY_DEFAULT = 0
    CATEGORY_FLAGGED = 1
    CATEGORY_PRIORITY = 2
    CATEGORY_QUALIFIED = 3

    CATEGORY_CHOICES = (
        (CATEGORY_DEFAULT, 'Default'),
        (CATEGORY_FLAGGED, 'Flagged'),
        (CATEGORY_PRIORITY, 'Priority'),
        (CATEGORY_QUALIFIED, 'Qualified'),
    )

    password = models.CharField(max_length=120, blank=True, null=True, default=None)

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)

    artist_name = models.CharField(max_length=120, blank=True, null=True)

    apple_id = models.CharField(max_length=120, blank=True, null=True)
    spotify_id = models.CharField(max_length=120, blank=True, null=True)

    category = models.PositiveSmallIntegerField(
        default=CATEGORY_DEFAULT, choices=CATEGORY_CHOICES
    )

    email = models.EmailField(max_length=120, blank=False, null=False, unique=True)
    email_verified = models.BooleanField(default=False)

    phone = models.CharField(max_length=120, blank=True, null=True, default=None)
    phone_verified = models.BooleanField(default=False)
    otp_enabled = models.BooleanField(
        default=False, help_text='Enable 2FA for user, requires verified phone number'
    )

    place_id = models.CharField(max_length=120, blank=True, null=True, default=None)

    country = models.CharField(max_length=2, blank=True, null=True, default=None)
    language = models.CharField(max_length=2, blank=True, null=True, default=None)

    facebook_id = models.CharField(
        max_length=32, blank=True, null=True, unique=True, default=None
    )
    google_id = models.CharField(
        max_length=32, blank=True, null=True, unique=True, default=None
    )
    apple_signin_id = models.CharField(
        max_length=64, blank=True, null=True, unique=True, default=None
    )

    profile_link = models.CharField(max_length=255, blank=True, null=True, default=None)
    profile_photo = models.CharField(
        max_length=512, blank=True, null=True, default=None
    )

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_frozen = models.BooleanField(default=False, verbose_name='Freeze')

    zendesk_id = models.BigIntegerField(blank=True, null=True, default=None)
    firebase_token = models.CharField(
        max_length=255, blank=True, null=True, default=None
    )

    spotify_page = models.CharField(max_length=255, null=True, blank=True)
    twitter_name = models.CharField(max_length=255, null=True, blank=True)
    facebook_page = models.CharField(max_length=255, null=True, blank=True)
    instagram_name = models.CharField(max_length=255, null=True, blank=True)
    soundcloud_page = models.CharField(max_length=255, null=True, blank=True)
    youtube_channel = models.CharField(max_length=255, null=True, blank=True)

    # Indicates that the user is an owner of at least one fuga release that was migrated
    fuga_migration = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    newsletter = models.BooleanField(default=False)

    objects = UserManager()

    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'email'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__original_artist_name = self.artist_name
        self.__original_email = self.email

    def __str__(self):
        return self.get_full_name()

    def __repr__(self):
        return '<{} #{}>'.format(self.__class__.__name__, self.pk)

    @property
    def name(self):
        return ' '.join((self.first_name, self.last_name))

    @property
    def is_anonymous(self):
        return False

    @property
    def is_authenticated(self):
        return True

    @property
    def is_superuser(self):
        return self.is_staff

    def _is_pro(self):
        return self.subscriptions.active().exists()

    _is_pro.boolean = True
    is_pro = cached_property(_is_pro, name="is_pro")

    @property
    def tier(self):
        active_subs = self.subscriptions.active()
        if not active_subs.exists():
            return self.TIER_FREE
        active_sub = active_subs.last()
        return active_sub.plan.tier

    @property
    def subscription_tier(self):
        """
        Used only for admin to display user tier
        """
        active_subs = self.subscriptions.active()
        if not active_subs.exists():
            return 'Free Tier'
        active_sub = active_subs.last()
        return active_sub.plan.get_tier_display()

    @property
    def is_gdpr_wiped(self):
        return (
            hasattr(self, 'usermetadata')
            and self.usermetadata.gdpr_wiped_at is not None
        )

    @property
    def is_delete_requested(self):
        return (
            hasattr(self, 'usermetadata')
            and self.usermetadata.is_delete_requested == True
        )

    def save(self, *args, **kwargs):
        is_adding = self._state.adding

        if self.is_password_changed():
            self.rotate_token()

        super().save(*args, **kwargs)

        if self.__original_artist_name != self.artist_name:
            logger.info(
                'User artist name changed from %s to %s',
                self.__original_artist_name,
                self.artist_name,
            )
            self.__original_artist_name = self.artist_name

        if self.is_email_changed():
            from amuse.tasks import send_email_verification_email

            send_email_verification_email.delay(self)
            if self.email_verified:
                self.email_verified = False
                super().save(update_fields=['email_verified'])
            self.__original_email = self.email

        if (is_adding or self.zendesk_id) and self.email and not settings.DEBUG:
            from amuse.tasks import zendesk_create_or_update_user

            zendesk_create_or_update_user.delay(self.id)

        if is_adding:
            Token.objects.create(user=self)

            if not self.is_admin():
                from amuse import tasks

                tasks.post_slack_user_created.delay(self)
                tasks.send_email_verification_email.delay(self)

            if not self.country and self.place_id:
                from amuse.places import get_country_by_place_id

                try:
                    self.country = get_country_by_place_id(self.place_id)
                    super().save(update_fields=['country'])
                except GooglePlacesError:
                    logger.error('GooglePlacesError for place_id: %s', self.place_id)

    def is_password_changed(self):
        new_password = self.password

        # only rotate token for valid passwords
        if not self.pk or not is_password_usable(new_password):
            return False
        try:
            old_password = User.objects.get(pk=self.pk).password
        except User.DoesNotExist:
            return False

        if new_password != old_password:
            return True

        return False

    def rotate_token(self):
        new_token = self.auth_token.generate_key()
        Token.objects.filter(user=self).update(key=new_token)

    def is_email_changed(self):
        return self.__original_email != self.email

    def get_balance(self):
        return (
            self.transactions.aggregate(models.Sum('amount')).get('amount__sum') or ZERO
        )

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def set_unusable_password(self):
        self.password = make_password(None)

    def check_password(self, raw_password):
        def setter(raw_password):
            self.set_password(raw_password)
            self.save(update_fields=['password'])

        return check_password(raw_password, self.password, setter)

    def is_admin(self):
        return self.is_staff

    def has_module_perms(self, app_label):
        return self.is_staff

    def has_perm(self, perm, obj=None):
        return self.is_staff

    def has_usable_password(self):
        return is_password_usable(self.password)

    def has_hyperwallet_token(self):
        if (
            hasattr(self, "usermetadata")
            and self.usermetadata.hyperwallet_user_token is not None
        ):
            return True
        else:
            return False

    def has_locked_splits(self):
        if self.royaltysplit_set.filter(is_locked=True).exists():
            return True
        return False

    has_locked_splits.boolean = True
    has_locked_splits.short_description = "In active FFWD Deal"

    def get_zendesk_url(self):
        zendesk_url = ''
        if self.zendesk_id:
            zendesk_url = (
                'https://amusesupport.zendesk.com/agent/users/%s/requested_tickets'
                % self.zendesk_id
            )

        return zendesk_url

    def get_mandrill_url(self):
        mandrill_url = 'https://mandrillapp.com/activity?q=full_email:%s' % self.email
        return mandrill_url

    def create_artist_v2(self, name, **kwargs):
        from users.models import ArtistV2, UserArtistRole

        artist = ArtistV2.objects.create(name=name, owner=self, **kwargs)

        self.userartistrole_set.create(artist=artist, type=UserArtistRole.OWNER)

        return artist

    def get_category_name(self):
        return self.get_category_display().lower()

    def get_username(self):
        return getattr(self, self.USERNAME_FIELD)

    def has_artist_with_spotify_id(self):
        return self.artists.filter(spotify_id__isnull=False).exists()

    def has_artist_with_audiomack_id(self):
        return self.artists.filter(audiomack_id__isnull=False).exists()

    def has_subscription_for_date(self, date):
        return self.subscriptions.active_for_date(date).exists()

    def get_tier_for_date(self, date):
        """
        Returns the User's Tier for the specified date.
        Used in Release admin pages.
        """

        subscription = (
            self.subscriptions.active_for_date(date).order_by('-valid_from').first()
        )
        if not subscription:
            return self.TIER_FREE

        return subscription.plan.tier

    def get_tier_display_for_date(self, date):
        """
        Returns the User's Tier name formatted for the specified date.
        Used in Release admin pages.
        """

        subscription = (
            self.subscriptions.active_for_date(date).order_by('-valid_from').first()
        )

        if not subscription:
            return 'Free Tier'

        return subscription.plan.get_tier_display()

    def is_free_trial_eligible(self):
        is_free_trial_used_before = self.subscriptions.filter(
            free_trial_from__isnull=False
        ).exists()

        return not is_free_trial_used_before

    def is_introductory_price_eligible(self):
        return not self.subscriptions.valid().exists()

    def current_entitled_subscription(self):
        """
        New version of `def current_subscription()`.
        This method use `Subscription.Status` as single source of truth to determine
        if user is FREE or BOOST/PRO.

        Dates (`valid_from`, `valid_until`, `grace_period_until`,
        `transaction.paid_until`) are ignored here.

        Other parts of the amuse-django system (payment_provider-to-amuse real time
        notifications, renewal cron jobs, etc.) takes dates into the calculation
        and sets `status` appropriately.
        """
        return self.subscriptions.active().last()

    def current_subscription(self):
        """
        Same as `current_entitled_subscription`.
        """
        return self.current_entitled_subscription()

    def is_free_trial_active(self):
        sub = self.current_entitled_subscription()

        if sub is None:
            return False

        return sub.is_free_trial_active()

    def is_member_of_artist_team(self, artist):
        try:
            return self.userartistrole_set.filter(artist=artist).exists()
        except:
            return False

    def is_admin_of_artist_team(self, artist):
        try:
            return self.userartistrole_set.filter(
                artist=artist, type__in=[UserArtistRole.OWNER, UserArtistRole.ADMIN]
            ).exists()
        except:
            return False

    @property
    def main_artist_profile(self):
        main_artist_profiles_uar = (
            self.userartistrole_set.values('artist_id')
            .filter(main_artist_profile=True)
            .first()
        )
        if main_artist_profiles_uar:
            return main_artist_profiles_uar.get('artist_id', None)

    def masked_phone(self):
        if self.phone is None or len(self.phone) < 7:
            return '***'

        cutoff = self.phone[0] == '+' and 3 or 2
        masked_part = (len(self.phone) - 4 - cutoff) * '*'
        return self.phone[:cutoff] + masked_part + self.phone[-4:]

    def flag_for_fraud(self):
        UserMetadata.objects.update_or_create(
            user=self, defaults={'is_fraud_attempted': True}
        )
        self.disable_subscription()

    def disable_subscription(self):
        subscription = self.current_subscription()
        if subscription and not subscription.valid_until:
            subscription.valid_until = subscription.paid_until
            subscription.save()

    def get_flagged_reason(self):
        try:
            metadata = self.usermetadata
            return metadata.flagged_reason_display if metadata else None
        except UserMetadata.DoesNotExist:
            return None

    @property
    def is_fraud_attempted(self):
        if hasattr(self, 'usermetadata'):
            return self.usermetadata.is_fraud_attempted
        return False

    @property
    def hyperwallet_integration(self):
        return "direct"

    @property
    def payee_profile_exist(self):
        return hasattr(self, 'payee')

    def flag_for_delete(self):
        defaults = {'is_delete_requested': True, 'delete_requested_at': datetime.now()}
        UserMetadata.objects.update_or_create(user=self, defaults=defaults)


class UserMetadata(models.Model):
    FLAGGED_REASON_STREAMFARMER = 0
    FLAGGED_REASON_SCAM = 1
    FLAGGED_REASON_SAMPLES = 2
    FLAGGED_REASON_INFRINGEMENTS = 3
    FLAGGED_REASON_INFRINGEMENTS_CLAIMS = 4
    FLAGGED_REASON_DMCA = 5
    FLAGGED_REASON_PAYMENT_FRAUD = 6
    FLAGGED_REASON_OTHER = 7
    FLAGGED_REASON_RESTRICTED_COUNTRY = 8

    FLAGGED_REASON_CHOICES = (
        (FLAGGED_REASON_STREAMFARMER, 'Streamfarmer'),
        (FLAGGED_REASON_SCAM, 'Scam'),
        (FLAGGED_REASON_SAMPLES, 'Samples'),
        (FLAGGED_REASON_INFRINGEMENTS, 'Infringements'),
        (FLAGGED_REASON_INFRINGEMENTS_CLAIMS, 'Infringements claims'),
        (FLAGGED_REASON_DMCA, 'DMCA'),
        (FLAGGED_REASON_PAYMENT_FRAUD, 'Payment Fraud'),
        (FLAGGED_REASON_OTHER, 'Other'),
        (FLAGGED_REASON_RESTRICTED_COUNTRY, 'Restricted country'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    apple_receipt = models.TextField(default='', blank=True)
    hyperwallet_user_token = models.CharField(max_length=50, null=True, blank=True)
    pro_trial_expiration_date = models.DateField(null=True, blank=True)
    flagged_reason = models.PositiveSmallIntegerField(
        null=True, choices=FLAGGED_REASON_CHOICES
    )
    impact_click_id = models.CharField(max_length=128, null=True, blank=True)
    flagged_at = models.DateTimeField(null=True)
    gdpr_wiped_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_delete_requested = models.BooleanField(default=False)
    delete_requested_at = models.DateTimeField(null=True, blank=True)
    is_fraud_attempted = models.BooleanField(
        default=False,
        help_text="When active, user is occasionally informed within the web app about payment fraud attempt. No other implications.",
    )

    @property
    def flagged_reason_display(self):
        try:
            return self.get_flagged_reason_display()
        except Exception:
            return None


class Comments(models.Model):
    user = models.OneToOneField(User, related_name='comments', on_delete=models.CASCADE)
    text = models.TextField(help_text='Internal comments about a user.')

    def __str__(self):
        return self.text


class UserGDPR(models.Model):
    """
    This model helps us save information during the GDPR Wipe Task
    """

    initiator = models.ForeignKey(
        User,
        related_name='usergdpr_initiator',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )
    user = models.ForeignKey(
        User,
        related_name='usergdpr_user',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )
    minfraud_entries = models.BooleanField(null=False, default=False)
    artist_v2_history_entries = models.BooleanField(null=False, default=False)
    user_history_entries = models.BooleanField(null=False, default=False)
    email_adress = models.BooleanField(null=False, default=False)
    user_first_name = models.BooleanField(null=False, default=False)
    user_last_name = models.BooleanField(null=False, default=False)
    user_social_links = models.BooleanField(null=False, default=False)
    user_artist_name = models.BooleanField(null=False, default=False)
    artist_v2_names = models.BooleanField(null=False, default=False)
    artist_v2_social_links = models.BooleanField(null=False, default=False)
    artist_v1_names = models.BooleanField(null=False, default=False)
    artist_v1_social_links = models.BooleanField(null=False, default=False)
    user_apple_signin_id = models.BooleanField(null=False, default=False)
    user_facebook_id = models.BooleanField(null=False, default=False)
    user_firebase_token = models.BooleanField(null=False, default=False)
    user_zendesk_id = models.BooleanField(null=False, default=False)
    transaction_withdrawals = models.BooleanField(null=False, default=False)
    user_isactive_deactivation = models.BooleanField(null=False, default=False)
    user_newsletter_deactivation = models.BooleanField(null=False, default=False)
    zendesk_data = models.BooleanField(null=False, default=False)
    segment_data = models.BooleanField(null=False, default=False)
    fuga_data = models.BooleanField(null=False, default=False)

    class Meta:
        verbose_name = 'GDPR Removal'
        verbose_name_plural = 'GDPR Removals'

    @classmethod
    def check_done(cls, user_id):
        values = cls.objects.filter(user_id=user_id).values().first().values()
        return False not in values


class OtpDevice(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    phone = models.CharField(max_length=120, db_index=True)
    otp_secret = models.CharField(max_length=16, blank=True)
    otp_counter = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False, help_text='Only used for signup')

    objects = OtpDeviceManager()

    def update_code(self):
        if not self.otp_secret:
            self.otp_secret = pyotp.random_base32()
            self.save()
        return self._current_code()

    def is_valid_code(self, code):
        is_valid = code == self._current_code()
        if is_valid:
            self.otp_counter += 1
            self.save()
        return is_valid

    def _current_code(self):
        return pyotp.HOTP(self.otp_secret).at(self.otp_counter)


class AppsflyerDevice(models.Model):
    appsflyer_id = models.CharField(max_length=64, primary_key=True, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Apple - iOS advertising IDs are called IDFA
    idfa = models.CharField(max_length=36, null=True, default=None)

    # Apple - identifier for vendor
    idfv = models.CharField(max_length=36, null=True, default=None)

    # Android - Advertisement ID
    aaid = models.CharField(max_length=36, null=True, default=None)

    # Android - Open Advertiser ID
    oaid = models.CharField(max_length=36, null=True, default=None)

    # Android - International Mobile Equipment Identity
    imei = models.CharField(max_length=20, null=True, default=None)

    updated = models.DateTimeField(auto_now=True, db_index=True)
