import enum
import json
from datetime import datetime, timedelta
from uuid import uuid4

from django.contrib import admin
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.forms import (
    ModelForm,
    ValidationError,
    IntegerField,
    CharField,
    Form,
    TextInput,
)
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from googleapiclient.errors import HttpError
from simple_history.admin import SimpleHistoryAdmin

from amuse.vendor.apple.subscriptions import AppleReceiptValidationAPIClient
from payments.models import PaymentTransaction, PaymentMethod
from subscriptions.helpers import renew_apple_subscription
from subscriptions.models import Subscription
from subscriptions.models import SubscriptionPlan, PriceCard, IntroductoryPriceCard
from subscriptions.vendor.google import PurchaseSubscription
from subscriptions.vendor.google.google_play_api import GooglePlayAPI
from subscriptions.vendor.google.processors.subscription_creator import (
    SubscriptionCreator,
)
from users.models import User


class GoogleSubscriptionActionError(Exception):
    pass


class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    fields = (
        'amount',
        'vat_amount',
        'paid_until',
        'status',
        'country',
        'external_transaction_id',
        'payment_transaction_link',
    )
    readonly_fields = ('payment_transaction_link',)
    extra = 0
    can_delete = False

    def payment_transaction_link(self, obj):
        return mark_safe(
            '<a href="%s" target="_blank">Open in new window</a>'
            % reverse('admin:payments_paymenttransaction_change', args=[obj.id])
        )

    payment_transaction_link.short_description = 'Link'


class SubscriptionForm(ModelForm):
    class Meta:
        model = Subscription
        fields = "__all__"

    def clean(self):
        if self.instance.provider == Subscription.PROVIDER_GOOGLE:
            raise ValidationError(
                "To change Google subscription, please use 'Action' dropdown from subscription list screen."
            )


@admin.register(Subscription)
class SubscriptionAdmin(SimpleHistoryAdmin):
    form = SubscriptionForm

    actions = [
        'poll_apple_receipt',
        'cancel_google_subscription',
        'defer_google_subscription',
        'refund_google_subscription',
        'revoke_google_subscription',
        'display_apple_receipt',
    ]
    list_display = (
        'user',
        'email',
        'plan',
        'valid_from',
        'valid_until',
        'provider',
        'status_list_display',
        'is_free_trial_active',
        'free_trial_from',
        'free_trial_until',
        'updated',
        'created',
    )
    list_filter = ('provider', 'status', 'plan')
    list_select_related = ('user',)
    raw_id_fields = ('payment_method', 'user')
    inlines = (PaymentTransactionInline,)
    search_fields = ('=user__id', '=user__email')
    history_list_display = ('valid_until', 'grace_period_until', 'status', 'plan')

    def status_list_display(self, subscription):
        return subscription.get_status_display().split(' ')[0]

    status_list_display.short_description = 'Status'

    def is_free_trial_active(self, obj):
        return obj.is_free_trial_active()

    is_free_trial_active.boolean = True

    def email(self, subscription):
        return subscription.user.email

    def cancel_google_subscription(self, request, qs):
        try:
            GoogleActionHelper().validate_single_item_selected(qs)
            GoogleActionHelper().validate_google_provider(qs)

            if not GoogleActionHelper().is_confirmed_by_jarvi5_user(request):
                return render(
                    request,
                    'admin/subscriptions/subscription/google_subscription_action.html',
                    context={
                        **self.admin_site.each_context(request),
                        'title': f'Cancel Google Subscription',
                        'media': self.media,
                        'opts': self.model._meta,
                        'subscription': qs.first(),
                        'action_name': 'cancel_google_subscription',
                        'description': [
                            "This action contacts Google.",
                            "Google cancels a user's subscription purchase.",
                            "Google subscription remains valid until its expiration time.",
                            "Once Amuse receive confirmation from the Google (usually after few seconds), valid_until date is set to expiration date.",
                        ],
                    },
                )

            GoogleActionHelper().cancel(qs)

            self.message_user(
                request,
                f"Cancel done. Subscription will be canceled once we receive confirmation from Google (refresh browser after few seconds).",
                messages.SUCCESS,
            )
        except GoogleSubscriptionActionError as ex:
            self.message_user(request, message=str(ex), level=messages.ERROR)

    cancel_google_subscription.short_description = "[Google] Cancel subscription"

    def defer_google_subscription(self, request, qs):
        try:
            GoogleActionHelper().validate_single_item_selected(qs)
            GoogleActionHelper().validate_google_provider(qs)
            GoogleActionHelper().validate_paid_until(qs)

            paid_until = qs.first().paid_until

            min_date = str(paid_until + timedelta(days=1))
            max_date = str(paid_until + timedelta(days=365))

            if not GoogleActionHelper().is_confirmed_by_jarvi5_user(request):
                return render(
                    request,
                    'admin/subscriptions/subscription/google_defer_action.html',
                    context={
                        **self.admin_site.each_context(request),
                        'title': f'Defer Google Subscription',
                        'media': self.media,
                        'opts': self.model._meta,
                        'subscription': qs.first(),
                        'expiry_date_default': min_date,
                        'expiry_date_min': min_date,
                        'expiry_date_max': max_date,
                        'action_name': 'defer_google_subscription',
                        'description': [
                            "This action contacts Google.",
                            "Google defers a user's subscription purchase until a specified future expiration time.",
                            "During the deferral period, the user is subscribed to your content with full access but is not charged. The subscription renewal date is updated to reflect the new date.",
                            "Deferred billing allows you to do the following:",
                            " - Give users free access as a special offer (such as giving one week free).",
                            " - Give free access to customers as a gesture of goodwill.",
                            "Billing can be deferred by as little as one day and by as long as one year.",
                            "Amuse subscription is updated once Amuse receive confirmation from the Google (usually after few seconds).",
                        ],
                    },
                )

            defer_date = request.POST.get('defer_date')

            GoogleActionHelper().validate_defer_date(defer_date)

            GoogleActionHelper().defer(qs, defer_date)

            self.message_user(
                request, f"Defer done. Subscription deferred.", messages.SUCCESS
            )
        except GoogleSubscriptionActionError as ex:
            self.message_user(request, message=str(ex), level=messages.ERROR)

    defer_google_subscription.short_description = "[Google] Defer subscription"

    def refund_google_subscription(self, request, qs):
        try:
            GoogleActionHelper().validate_single_item_selected(qs)
            GoogleActionHelper().validate_google_provider(qs)

            if not GoogleActionHelper().is_confirmed_by_jarvi5_user(request):
                return render(
                    request,
                    'admin/subscriptions/subscription/google_subscription_action.html',
                    context={
                        **self.admin_site.each_context(request),
                        'title': f'Refund Google Subscription',
                        'media': self.media,
                        'opts': self.model._meta,
                        'subscription': qs.first(),
                        'action_name': 'refund_google_subscription',
                        'description': [
                            "This action contacts Google.",
                            "Google refunds a user's subscription purchase, but the subscription remains valid until its expiration time and it will continue to recur.",
                            "There is no visible change in Jarvi5.",
                        ],
                    },
                )

            GoogleActionHelper().refund(qs)

            self.message_user(
                request, f"Refund done. Subscription remains active.", messages.SUCCESS
            )
        except GoogleSubscriptionActionError as ex:
            self.message_user(request, message=str(ex), level=messages.ERROR)

    refund_google_subscription.short_description = (
        "[Google] Refund subscription but remain active"
    )

    def revoke_google_subscription(self, request, qs):
        try:
            GoogleActionHelper().validate_single_item_selected(qs)
            GoogleActionHelper().validate_google_provider(qs)

            if not GoogleActionHelper().is_confirmed_by_jarvi5_user(request):
                return render(
                    request,
                    'admin/subscriptions/subscription/google_subscription_action.html',
                    context={
                        **self.admin_site.each_context(request),
                        'title': f'Revoke Google Subscription',
                        'media': self.media,
                        'opts': self.model._meta,
                        'subscription': qs.first(),
                        'action_name': 'revoke_google_subscription',
                        'description': [
                            "This action contacts Google.",
                            "Google refunds and immediately revokes a user's subscription purchase.",
                            "Google will terminate immediately access to the subscription and it will stop recurring.",
                            "Once Amuse receive confirmation from the Google (usually after few seconds), subscription will be terminated on Amuse.",
                        ],
                    },
                )

            GoogleActionHelper().revoke(qs)

            self.message_user(
                request,
                f"Revoke done. Subscription status will be changed to EXPIRED once we receive confirmation from Google (refresh browser after few seconds).",
                messages.SUCCESS,
            )
        except GoogleSubscriptionActionError as ex:
            self.message_user(request, message=str(ex), level=messages.ERROR)

    revoke_google_subscription.short_description = (
        "[Google] Refund and immediately revoke subscription"
    )

    def poll_apple_receipt(self, request, qs):
        subscriptions = qs.filter(provider=Subscription.PROVIDER_IOS).select_related(
            'user'
        )
        count = subscriptions.count()

        if request.method == 'POST' and request.POST.get('confirm', '') == 'yes':
            success_count = 0
            fail_count = 0
            for subscription in subscriptions:
                is_success = renew_apple_subscription(
                    subscription, False, PaymentTransaction.PLATFORM_ADMIN
                )
                if is_success:
                    success_count += 1
                else:
                    fail_count += 1

            self.message_user(
                request,
                f'{count} Apple subscriptions polled. Succeeded: {success_count}, failed: {fail_count}',
            )
            return HttpResponseRedirect(request.get_full_path())

        return render(
            request,
            'admin/subscriptions/subscription/poll_apple_receipt.html',
            context={
                **self.admin_site.each_context(request),
                'title': f'Poll {count} Apple subscriptions?',
                'media': self.media,
                'opts': self.model._meta,
                'subscriptions': subscriptions,
            },
        )

    def display_apple_receipt(self, request, qs):
        subscription = qs.filter(provider=Subscription.PROVIDER_IOS).first()
        if not subscription:
            self.message_user(
                request, f'Non Apple subscription is selected', messages.WARNING
            )
            return HttpResponseRedirect(request.get_full_path())
        try:
            receipt = subscription.apple_receipt()
            client = AppleReceiptValidationAPIClient(receipt, max_retries=1)
            client.validate_receipt()
            data = client.response_data
            data_pretty = json.dumps(data, indent=4)
        except Exception as e:
            data_pretty = '{"ERROR":%s}' % e
        return render(
            request,
            'admin/subscriptions/subscription/display_apple_receipt.html',
            context={
                **self.admin_site.each_context(request),
                'media': self.media,
                'opts': self.model._meta,
                'receipt_data': data_pretty,
            },
        )

    def get_urls(self):
        urls = super().get_urls()
        url_name_base = f'{self.model._meta.app_label}_{self.model._meta.model_name}'
        url_name_replace = f'{url_name_base}_google'

        urls = [
            path(
                'google-recreate-subscription/',
                self.google_recreate_subscription,
                name=url_name_replace,
            )
        ] + urls
        return urls

    def google_recreate_subscription(self, request):
        step = GoogleRecreateHelper.get_step(request)

        if step == GoogleRecreateHelper.StepEnum.VALIDATION:
            form = GoogleRecreateForm(request.POST)

            if form.is_valid():
                form.fields['user_id'].widget.attrs['readonly'] = True
                form.fields['google_product_id'].widget.attrs['readonly'] = True
                form.fields['purchase_token'].widget.attrs['readonly'] = True

                return render(
                    request,
                    'admin/subscriptions/subscription/google_recreate_subscription_form.html',
                    context={
                        **self.admin_site.each_context(request),
                        'form': form,
                        'title': f'Recreate Google Subscription (Preview)',
                        'media': self.media,
                        'opts': self.model._meta,
                        'step': int(GoogleRecreateHelper.StepEnum.VALIDATION),
                        'preview_items': GoogleRecreateHelper.preview_items(form),
                    },
                )
        elif step == GoogleRecreateHelper.StepEnum.CONFIRMATION:
            form = GoogleRecreateForm(request.POST)
            if form.is_valid():
                subscription = GoogleRecreateHelper.create_subscription(form)

                url = reverse(
                    'admin:subscriptions_subscription_change', args=[subscription.pk]
                )
                url_string = f'<a href="{url}" target="_blank">{subscription}</a>'

                messages.info(request, mark_safe(f'Subscription created: {url_string}'))
                return HttpResponseRedirect(url)
        else:
            form = GoogleRecreateForm()

        return render(
            request,
            'admin/subscriptions/subscription/google_recreate_subscription_form.html',
            context={
                **self.admin_site.each_context(request),
                'form': form,
                'title': f'Recreate Google Subscription (Input)',
                'media': self.media,
                'opts': self.model._meta,
                'step': int(GoogleRecreateHelper.StepEnum.INITIAL),
            },
        )


class GoogleRecreateForm(Form):
    user_id = IntegerField(required=True, label='User ID', min_value=1)
    google_product_id = CharField(
        required=True, widget=TextInput(attrs={'size': '128'})
    )

    purchase_token = CharField(required=True, widget=TextInput(attrs={'size': '128'}))

    def clean(self):
        GoogleRecreateHelper().validate(self)

        return super(GoogleRecreateForm, self).clean()


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'period',
        'trial_days',
        'is_public',
        'apple_product_id',
        'apple_product_id_notrial',
        'apple_product_id_introductory',
        'google_product_id',
        'google_product_id_trial',
        'google_product_id_introductory',
        'tier',
    )
    list_filter = ('is_public',)
    fields = (
        'name',
        'trial_days',
        'grace_period_days',
        'is_public',
        'apple_product_id',
        'apple_product_id_notrial',
        'apple_product_id_introductory',
        'google_product_id',
        'google_product_id_trial',
        'google_product_id_introductory',
        'period',
        'tier',
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('period',)
        return self.readonly_fields


class PriceCardAdminForm(ModelForm):
    class Meta:
        model = PriceCard
        fields = "__all__"

    def clean(self):
        obj_id = 0 if self.instance.pk is None else self.instance.pk
        provided_plan = self.cleaned_data.get('plan')
        provided_countries = self.cleaned_data.get('countries')
        PriceCardValidator().validate_price_cards(
            provided_plan, provided_countries, obj_id
        )
        return super(PriceCardAdminForm, self).clean()


@admin.register(PriceCard)
class PriceCardAdmin(admin.ModelAdmin):
    form = PriceCardAdminForm

    list_display = (
        'get_plan',
        'price',
        'period_price',
        'get_currency',
        'get_countries',
    )
    list_filter = ('plan', 'currency', 'countries')
    filter_horizontal = ('countries',)
    actions = ['action_create_introductory_price']

    def get_plan(self, card):
        return card.plan.name

    get_plan.admin_order_field = 'plan__name'
    get_plan.short_description = 'Plan Name'

    def get_currency(self, card):
        return card.currency.code

    get_currency.admin_order_field = 'currency__code'
    get_currency.short_description = 'Currency'

    def get_countries(self, card):
        return ', '.join([country.code for country in card.countries.all()])

    get_countries.short_description = 'Countries'

    def action_create_introductory_price(self, request, qs):
        if not CreateIntroductoryPriceCardsHelper().is_confirmed_by_jarvi5_user(
            request
        ):
            min_date = str(timezone.now().date())
            start_date = str(timezone.now().date() + timedelta(days=1))
            end_date = str(timezone.now().date() + timedelta(days=366))
            return render(
                request,
                'admin/subscriptions/subscription/create_introductory_price_cards.html',
                context={
                    **self.admin_site.each_context(request),
                    'title': f'Create Introductory Price Cards',
                    'media': self.media,
                    'opts': self.model._meta,
                    'price_cards': qs.all(),
                    'start_date_default': start_date,
                    'start_date_min': min_date,
                    'end_date_default': end_date,
                    'end_date_min': min_date,
                    'action_name': 'action_create_introductory_price',
                    'description': [
                        "This action use PriceCard(s) as a template to create IntroductoryPriceCard(s).",
                        "PriceCard values are used to create IntroductoryPriceCard.",
                        "In step #1 set common values. Common values are shared across Introductory Price Cards ",
                        "In step #2 set price for each Introductory Price Card.",
                        "In step #3 confirm your selection.",
                    ],
                },
            )

        @transaction.atomic
        def create_introductory_prices(request, qs):
            try:
                created_offers = []
                start_date = request.POST.get(f'start_date')
                end_date = request.POST.get(f'end_date')

                for price_card in qs.all():
                    intro_offer = IntroductoryPriceCard(
                        plan=price_card.plan,
                        price=request.POST.get(
                            f'new_price_{price_card.pk}', price_card.price
                        ),
                        currency=price_card.currency,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    intro_offer.save()
                    intro_offer.countries.set(price_card.countries.all())

                    created_offers.append(intro_offer)

                urls = []
                for offer in created_offers:
                    url = f'<a href="{reverse("admin:subscriptions_introductorypricecard_change", args=[offer.id])}" target="_blank">{offer}</a>'
                    urls.append(url)

                self.message_user(
                    request,
                    message=mark_safe(f'Successfully created: {", ".join(urls)}'),
                    level=messages.SUCCESS,
                )

            except Exception as ex:
                self.message_user(request, message=str(ex), level=messages.ERROR)

        create_introductory_prices(request, qs)

    action_create_introductory_price.short_description = (
        "Create Introductory Price Card(s)"
    )


class ActiveIntroductoryPriceCardFilter(admin.SimpleListFilter):
    parameter_name = 'is_active'
    title = 'Active'

    def lookups(self, request, model_admin):
        return (('active', 'Active'), ('inactive', 'Inactive'))

    def queryset(self, request, queryset):
        value = self.value()
        today = timezone.now().date()

        if value == 'active':
            return queryset.filter(start_date__lte=today, end_date__gte=today)

        if value == 'inactive':
            return queryset.filter(~Q(start_date__lte=today, end_date__gte=today))

        return queryset


class IntroductoryPriceCardAdminForm(ModelForm):
    class Meta:
        model = IntroductoryPriceCard
        fields = "__all__"

    def clean(self):
        obj_id = 0 if self.instance.pk is None else self.instance.pk
        provided_plan = self.cleaned_data.get('plan')
        provided_countries = self.cleaned_data.get('countries')
        PriceCardValidator().validate_introductory_price_cards(
            provided_plan, provided_countries, obj_id
        )
        return super(IntroductoryPriceCardAdminForm, self).clean()


@admin.register(IntroductoryPriceCard)
class IntroductoryPriceCardAdmin(PriceCardAdmin):
    form = IntroductoryPriceCardAdminForm

    def get_list_display(self, request):
        return self.list_display + ('period', 'is_active', 'start_date', 'end_date')

    def get_list_filter(self, request):
        return (ActiveIntroductoryPriceCardFilter,) + self.list_filter

    def is_active(self, card):
        return card.start_date <= timezone.now().date() <= card.end_date

    is_active.boolean = True

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'action_create_introductory_price' in actions:
            del actions['action_create_introductory_price']
        return actions


class GoogleActionHelper(object):
    @staticmethod
    def is_confirmed_by_jarvi5_user(request):
        return request.method == 'POST' and request.POST.get('confirm', '') == 'yes'

    @staticmethod
    def validate_defer_date(defer_date_string):
        if not defer_date_string:
            raise GoogleSubscriptionActionError('Defer date not set.')

        try:
            DATE_FORMAT = '%Y-%m-%d'
            defer_date = datetime.strptime(defer_date_string, DATE_FORMAT)
        except ValueError as err:
            raise GoogleSubscriptionActionError(
                f'Not able to parse defer date. {str(err)}'
            )

    @staticmethod
    def validate_google_provider(qs):
        subscription = qs.first()
        if subscription.provider != Subscription.PROVIDER_GOOGLE:
            raise GoogleSubscriptionActionError('Please, select Google subscription.')

    @staticmethod
    def validate_paid_until(qs):
        subscription = qs.first()
        if not subscription.paid_until:
            raise GoogleSubscriptionActionError(
                f"Unable to change subscription. Invalid paid_until date."
            )

    @staticmethod
    def validate_purchase(event_id, purchase):
        if not purchase:
            raise GoogleSubscriptionActionError(
                f"Event ID={event_id}. Unable to verify purchase token."
            )

    @staticmethod
    def validate_result(event_id, result):
        if not result['success']:
            raise GoogleSubscriptionActionError(
                f"Event ID={event_id}. Google: {result['message']}"
            )

    @staticmethod
    def validate_single_item_selected(qs):
        if qs.count() != 1:
            raise GoogleSubscriptionActionError(
                'Please, select only one Google subscription.'
            )

    @staticmethod
    def get_google_product_id(subscription):
        if subscription.is_free_trial():
            return subscription.plan.google_product_id_trial

        product_id = subscription.get_google_product_id()
        if product_id is not None:
            return product_id

        return subscription.plan.google_product_id

    def cancel(self, qs):
        event_id = str(uuid4()).replace('-', '')
        subscription = qs.first()

        google_product_id = self.get_google_product_id(subscription)

        result = GooglePlayAPI().cancel(
            event_id,
            google_product_id,
            subscription.payment_method.external_recurring_id,
        )

        self.validate_result(event_id, result)

    def defer(self, qs, defer_date_string):
        event_id = str(uuid4()).replace('-', '')
        subscription = qs.first()
        google_product_id = self.get_google_product_id(subscription)

        purchase = GooglePlayAPI().verify_purchase_token(
            event_id,
            google_product_id,
            subscription.payment_method.external_recurring_id,
        )

        self.validate_purchase(event_id, purchase)

        expiry_timestamp = purchase.get('expiryTimeMillis')

        DATE_FORMAT = '%Y-%m-%d'
        defer_date = datetime.strptime(defer_date_string, DATE_FORMAT)
        defer_timestmap = int(defer_date.timestamp() * 1000)
        google_product_id = self.get_google_product_id(subscription)

        result = GooglePlayAPI().defer(
            event_id,
            google_product_id,
            subscription.payment_method.external_recurring_id,
            expiry_timestamp,
            defer_timestmap,
        )

        self.validate_result(event_id, result)

    def refund(self, qs):
        event_id = str(uuid4()).replace('-', '')
        subscription = qs.first()
        google_product_id = self.get_google_product_id(subscription)

        result = GooglePlayAPI().refund(
            event_id,
            google_product_id,
            subscription.payment_method.external_recurring_id,
        )

        self.validate_result(event_id, result)

    def revoke(self, qs):
        event_id = str(uuid4()).replace('-', '')
        subscription = qs.first()
        google_product_id = self.get_google_product_id(subscription)

        result = GooglePlayAPI().revoke(
            event_id,
            google_product_id,
            subscription.payment_method.external_recurring_id,
        )

        self.validate_result(event_id, result)


class GoogleRecreateHelper(object):
    class StepEnum(enum.IntEnum):
        INITIAL = 0
        VALIDATION = 1
        CONFIRMATION = 2

    @staticmethod
    def get_step(request):
        step = int(request.POST.get('step', 0))
        if request.method == 'POST' and step == int(
            GoogleRecreateHelper.StepEnum.CONFIRMATION
        ):
            return GoogleRecreateHelper.StepEnum.CONFIRMATION

        if request.method == 'POST':
            return GoogleRecreateHelper.StepEnum.VALIDATION

        return GoogleRecreateHelper.StepEnum.INITIAL

    @staticmethod
    def preview_items(form: GoogleRecreateForm):
        user_id = form.cleaned_data['user_id']
        google_product_id = form.cleaned_data['google_product_id']
        purchase_token = form.cleaned_data['purchase_token']
        event_id = str(uuid4()).replace('-', '')
        purchase = GooglePlayAPI().verify_purchase_token(
            event_id, google_product_id, purchase_token
        )
        gp = PurchaseSubscription(**purchase)
        preview_items = [
            {
                'name': 'order_id',
                'label': 'Order ID',
                'value': gp.order_id,
                'help': 'The order id of the latest recurring order associated with the purchase of the subscription.',
            },
            {
                'name': 'start_time',
                'label': 'Start Time',
                'value': gp.start,
                'help': 'Time at which the subscription was granted',
            },
            {
                'name': 'expiry_time',
                'label': 'Expiry Time',
                'value': gp.expiry_date,
                'help': 'Expiry time in date format',
            },
            {
                'name': 'auto_renewing',
                'label': 'Auto Renewing',
                'value': gp.auto_renewing,
                'help': 'Whether the subscription will automatically be renewed when it reaches its current expiry time',
            },
            {
                'name': 'cancel_reason',
                'label': 'Cancel Reason',
                'value': gp.cancel_reason,
                'help': 'The reason why a subscription was canceled or is not auto-renewing.',
            },
            {
                'name': 'price_amount',
                'label': 'Price',
                'value': gp.price_amount,
                'help': 'Price of the subscription, not including tax',
            },
            {
                'name': 'price_currency_code',
                'label': 'Currency Code',
                'value': gp.price_currency_code,
                'help': 'ISO 4217 currency code for the subscription price',
            },
            {
                'name': 'country_code',
                'label': 'Country Code',
                'value': gp.country_code,
                'help': 'ISO 3166-1 alpha-2 billing country/region code of the user at the time the subscription was granted.',
            },
            {
                'name': 'linked_purchase_token',
                'label': 'Linked Purchase Token',
                'value': gp.linked_purchase_token,
                'help': 'The purchase token of the originating purchase if this subscription is one of the following: 1. Upgrade/downgrade from a previous subscriptionl; 2. Re-signup of a canceled but non-lapsed subscription',
            },
            {
                'name': 'obfuscated_external_account_id',
                'label': 'Obfuscated External Account ID',
                'value': gp.obfuscated_external_account_id,
                'help': 'An obfuscated version of the id that is uniquely associated with the user'
                's account in your app',
            },
        ]
        return preview_items

    @staticmethod
    def create_subscription(form: GoogleRecreateForm):
        user_id = form.cleaned_data['user_id']
        google_product_id = form.cleaned_data['google_product_id']
        purchase_token = form.cleaned_data['purchase_token']

        event_id = str(uuid4()).replace('-', '')
        user = User.objects.get(pk=user_id)

        return SubscriptionCreator().create_from_admin(
            event_id, user, google_product_id, purchase_token
        )

    @staticmethod
    def validate(form: GoogleRecreateForm):
        if not form.is_valid():
            return super(GoogleRecreateForm, form).clean()

        user_id = form.cleaned_data.get('user_id', None)
        purchase_token = form.cleaned_data['purchase_token']
        google_product_id = form.cleaned_data['google_product_id']

        user = User.objects.filter(pk=user_id).first()
        if user is None:
            form.add_error('user_id', 'User does not exist.')

        plan = SubscriptionPlan.objects.get_by_google_product_id(google_product_id)
        if plan is None:
            form.add_error('google_product_id', 'Unknown Google Product ID.')

        payment_method = PaymentMethod.objects.filter(
            external_recurring_id=purchase_token
        ).first()
        if payment_method:
            url = reverse(
                'admin:payments_paymentmethod_change', args=[payment_method.id]
            )

            payment_method_url = (
                f'<a href="{url}" target="_blank">{payment_method.pk}</a>'
            )

            subscription = Subscription.objects.filter(
                payment_method=payment_method
            ).first()

            sub_info = ''
            if subscription:
                url = reverse(
                    'admin:subscriptions_subscription_change', args=[payment_method.id]
                )
                subscription_url = f'<a href="{url}" target="_blank">{subscription}</a>'
                sub_info = f', (Subscription: {subscription_url})'

            form.add_error(
                'purchase_token',
                mark_safe(
                    f'Purchase token already used: Payment Method: {payment_method_url} {sub_info}'
                ),
            )

        try:
            event_id = str(uuid4()).replace('-', '')
            purchase = GooglePlayAPI().verify_purchase_token(
                event_id, google_product_id, purchase_token, raise_exception=True
            )
        except HttpError as e:
            form.add_error('purchase_token', str(e.error_details))


class CreateIntroductoryPriceCardsHelper(object):
    @staticmethod
    def is_confirmed_by_jarvi5_user(request):
        return request.method == 'POST' and request.POST.get('confirm', '') == 'yes'


class PriceCardValidator:
    @staticmethod
    def validate_price_cards(provided_plan, provided_countries, obj_id):
        price_cards_duplicates = list(
            PriceCard.objects.filter(
                ~Q(pk=obj_id),
                plan__pk=provided_plan.pk,
                countries__in=provided_countries,
            )
            .values('plan', 'countries', 'countries__name')
            .annotate(count=Count('countries'))
            .order_by('-count')
            .filter(count__gt=0)
        )

        if len(price_cards_duplicates) > 0:
            raise ValidationError(
                PriceCardValidator().create_human_readable_messages(
                    price_cards_duplicates
                )
            )

    @staticmethod
    def validate_introductory_price_cards(provided_plan, provided_countries, obj_id):
        intro_price_cards_duplicates = list(
            IntroductoryPriceCard.objects.filter(
                ~Q(pk=obj_id),
                plan__pk=provided_plan.pk,
                countries__in=provided_countries,
            )
            .values('plan', 'countries', 'countries__name')
            .annotate(count=Count('countries'))
            .order_by('-count')
            .filter(count__gt=0)
        )

        if len(intro_price_cards_duplicates) > 0:
            raise ValidationError(
                PriceCardValidator().create_human_readable_messages(
                    intro_price_cards_duplicates
                )
            )

    @staticmethod
    def create_human_readable_messages(duplicates):
        by_plan = dict()
        for item in duplicates:
            by_plan.setdefault(item['plan'], list()).append(item['countries__name'])

        error_messages = list()
        for plan_id, countries__name in by_plan.items():
            plan = SubscriptionPlan.objects.get(pk=plan_id)
            url = reverse('admin:subscriptions_subscriptionplan_change', args=[plan_id])
            url = mark_safe(f'<a href="{url}" target="_blank">{plan}</a>')
            countries_list = ', '.join(countries__name)
            err_msg = mark_safe(
                f'Following countries: {countries_list}, have been used more than once for the plan {url}'
            )
            error_messages.append(err_msg)

        return error_messages
