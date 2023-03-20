import binascii
import logging
import os
from copy import copy
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Q, Value, F
from django.db.models.functions import Concat
from django.forms import ModelForm
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from import_export import resources
from import_export.admin import ExportMixin
from rest_framework.authtoken.models import Token, TokenProxy

from amuse.analytics import user_frozen
from amuse.api.base.validators import validate_tiktok_name
from amuse.api.v4.serializers.subscription import AppleSubscriptionSerializer
from amuse.mails import send_password_reset

from releases.models import Release, ReleaseArtistRole, SongArtistRole
from users.bulk_edit_form import BulkEditField, BulkEditForm
from users.gdpr import launch_gdpr_tasks
from users.helpers import send_royalty_invite
from users.models import (
    ArtistV2,
    Comments,
    LegacyRoyaltyAdvance,
    RoyaltyInvitation,
    Transaction,
    TransactionDeposit,
    TransactionFile,
    TransactionSource,
    TransactionWithdrawal,
    User,
    UserArtistRole,
    UserGDPR,
    UserMetadata,
)
from users.utils import parse_input_string_to_digits

admin.site.unregister(TokenProxy)

logger = logging.getLogger(__name__)


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    actions = ["action_rotate"]
    search_fields = ["=user__id"]
    raw_id_fields = ["user"]
    readonly_fields = ["key"]
    list_display = ["user", "key"]

    def action_rotate(self, request, qs):
        rotate_auth_token(qs)

    action_rotate.short_description = "Rotate auth key"


class UserForm(ModelForm):
    category = forms.TypedChoiceField(choices=User.CATEGORY_CHOICES, coerce=int)
    flagged_reason = forms.TypedChoiceField(
        required=False,
        choices=(('', '---------------------'),) + UserMetadata.FLAGGED_REASON_CHOICES,
        coerce=int,
        label='New flagged reason',
        help_text='Leave this field empty unless you want to change the current Flagged reason (that is shown under \'User Metadata\'), or change user\'s Category to Flagged. ',
    )

    class Meta:
        model = User
        fields = '__all__'

    def clean_email(self):
        return self.cleaned_data['email'] or None

    def clean_facebook_id(self):
        return self.cleaned_data['facebook_id'] or None

    def clean_google_id(self):
        return self.cleaned_data['google_id'] or None

    def clean(self):
        is_flagged = self.cleaned_data.get('category') == User.CATEGORY_FLAGGED
        flagged_reason = self.cleaned_data.get('flagged_reason')

        # flagged_reason will evaluate to False when it has a value of 0,
        # which we don't want it to be. Hence, adding the 0 check.
        if not flagged_reason == 0 and not flagged_reason:
            self.cleaned_data['flagged_reason'] = None
            flagged_reason = None

        existing_metadata = UserMetadata.objects.filter(
            user_id=self.instance.pk
        ).first()

        if existing_metadata:
            flagged_reason_db = existing_metadata.flagged_reason
        else:
            flagged_reason_db = None

        if is_flagged and flagged_reason is None and flagged_reason_db is None:
            raise forms.ValidationError(
                'Flagged reason must be specified when the Category is \'Flagged\'. '
            )

        if not is_flagged and flagged_reason is not None:
            raise forms.ValidationError(
                'Category must be \'Flagged\' if you specify a Flagged reason. '
            )

        if flagged_reason_db == flagged_reason:
            self.cleaned_data['flagged_reason'] = flagged_reason_db

        super().clean()

    def save(self, commit=True):
        instance = super().save(commit=commit)
        flagged_reason = self.cleaned_data.get('flagged_reason')

        if self.cleaned_data['category'] == User.CATEGORY_FLAGGED:
            if flagged_reason or flagged_reason == 0:
                UserMetadata.objects.update_or_create(
                    defaults={
                        'flagged_reason': self.cleaned_data['flagged_reason'],
                        'flagged_at': timezone.now(),
                    },
                    user=instance,
                )
        else:
            UserMetadata.objects.update_or_create(
                defaults={
                    'flagged_reason': self.cleaned_data['flagged_reason'],
                    'flagged_at': None,
                },
                user=instance,
            )
        return instance


class BulkEditUserForm(BulkEditForm):
    is_active = BulkEditField(forms.BooleanField(required=False))
    category = BulkEditField(
        forms.TypedChoiceField(
            required=False, choices=User.CATEGORY_CHOICES, coerce=int
        )
    )
    flagged_reason = BulkEditField(
        forms.TypedChoiceField(
            required=False,
            choices=(('', '---------------------'),)
            + UserMetadata.FLAGGED_REASON_CHOICES,
            empty_value=None,
            coerce=int,
        ),
        help_text='Must be used in combination with the "category" field.',
    )

    is_frozen = BulkEditField(forms.BooleanField(required=False))
    comment = BulkEditField(
        forms.CharField(required=False, widget=forms.Textarea),
        help_text='Internal comments about a user.',
    )

    def clean(self):
        is_category_edited = 'category' in self.cleaned_data
        category = self.cleaned_data.get('category')

        flagged_reasons = dict(UserMetadata.FLAGGED_REASON_CHOICES).keys()
        is_flagged_reason_edited = 'flagged_reason' in self.cleaned_data
        flagged_reason = self.cleaned_data.get('flagged_reason')

        def validation_rule1():
            if is_category_edited is False and flagged_reason is not None:
                raise forms.ValidationError(
                    'Flagged reason must not be specified if the category is not updated.'
                )

        def validation_rule2():
            is_flagged = category == User.CATEGORY_FLAGGED
            without_specified_reason = flagged_reason not in flagged_reasons
            if is_flagged and without_specified_reason:
                raise forms.ValidationError(
                    'Flagged reason must be specified if the category is Flagged.'
                )

        def validation_rule3():
            if is_category_edited is False:
                return

            if category == User.CATEGORY_FLAGGED:
                return

            if is_flagged_reason_edited and flagged_reason is not None:
                raise forms.ValidationError(
                    'Flagged reason must be empty if the category is not Flagged.'
                )

            if is_flagged_reason_edited is False:
                raise forms.ValidationError(
                    'Flagged reason must be cleared if the category is not Flagged.'
                )

        [rule() for rule in [validation_rule1, validation_rule2, validation_rule3]]
        super().clean()

    @transaction.atomic
    def bulk_update(self, request, qs):
        users = qs.all()

        # update flagged_reasons
        if 'flagged_reason' in self.cleaned_data:
            flagged_reason = self.cleaned_data.pop('flagged_reason')
            for user in users:
                UserMetadata.objects.update_or_create(
                    defaults={'flagged_reason': flagged_reason}, user=user
                )

        # update comments
        if 'comment' in self.cleaned_data:
            comment = self.cleaned_data.pop('comment')
            for user in users:
                if Comments.objects.filter(user=user).exists():
                    # append comment
                    Comments.objects.filter(user=user).update(
                        text=Concat(F('text'), Value('\n'), Value(comment))
                    )
                else:
                    Comments.objects.create(user=user, text=comment)

        # update users
        super(BulkEditUserForm, self).bulk_update(request, qs)


class CommentsInline(admin.StackedInline):
    model = Comments
    fields = ('text',)
    extra = 1


class UserArtistRoleFormSet(forms.models.BaseInlineFormSet):
    class Meta:
        model = UserArtistRole
        fields = '__all__'

    def clean(self):
        if self.has_changed():  # perform this check only if UAR have changed
            self._verify_only_one_owner()
            self._verify_only_one_main_artist_profile()

    def _verify_only_one_main_artist_profile(self):
        map_count = len(
            [
                form
                for form in self.forms
                if form.cleaned_data['main_artist_profile'] is True
            ]
        )
        if map_count > 1:
            raise forms.ValidationError("Artist can only have one Main Artist Profile")

    def _verify_only_one_owner(self):
        changed_forms = [
            form
            for form in self.forms
            if (
                form.has_changed() and form.cleaned_data['type'] == UserArtistRole.OWNER
            )
        ]
        for form in changed_forms:
            artist = form.cleaned_data['artist']
            user = form.cleaned_data['user']

            # check if owner is set on the artist model
            if artist.owner and artist.owner != user:
                raise forms.ValidationError("Artist already has an OWNER")

            # check if there's already owner role
            has_owner = artist.userartistrole_set.filter(
                type=UserArtistRole.OWNER
            ).exists()
            is_deleting = 'DELETE' in form.fields and form.fields['DELETE']
            if has_owner and not is_deleting:
                raise forms.ValidationError("Artist can only have one OWNER user")


class UserArtistRoleInline(admin.StackedInline):
    formset = UserArtistRoleFormSet
    model = UserArtistRole
    fields = ('user', 'artist', 'type', 'main_artist_profile', 'created')
    raw_id_fields = ('artist', 'user')
    readonly_fields = ('created',)
    extra = 0


class UserMetadataInline(admin.StackedInline):
    model = UserMetadata
    readonly_fields = (
        'apple_receipt',
        'flagged_reason',
        'flagged_at',
        'delete_requested_at',
    )
    exclude = ('hyperwallet_user_token',)
    can_delete = False


class UserResource(resources.ModelResource):
    class Meta:
        model = User
        fields = (
            'id',
            'name',
            'artist_name',
            'comments',
            'email',
            'phone',
            'profile_link',
            'created',
        )


class HasAppleReceipt(admin.SimpleListFilter):
    parameter_name = 'apple_receipt'
    title = 'unverified Apple IAP'

    def lookups(self, request, model_admin):
        return (('1', 'Yes'), ('0', 'No'))

    def queryset(self, request, queryset):
        receipt_query = Q(usermetadata__apple_receipt="") | Q(usermetadata=None)
        value = self.value()
        if value == '1':
            return queryset.exclude(receipt_query)
        elif value == '0':
            return queryset.filter(receipt_query)
        return queryset


class InputFilter(admin.SimpleListFilter):
    template = 'admin/input_filter.html'

    def lookups(self, request, model_admin):
        # Dummy, required to show the filter.
        return ((),)

    def choices(self, changelist):
        # Grab only the "all" option.
        all_choice = next(super().choices(changelist))
        all_choice['query_parts'] = (
            (k, v)
            for k, v in changelist.get_filters_params().items()
            if k != self.parameter_name
        )
        yield all_choice


class UserIDFilter(InputFilter):
    parameter_name = 'user'
    title = 'User IDs'

    def queryset(self, request, queryset):
        if self.value() is not None:
            ids = self.value()
            ids_list = parse_input_string_to_digits(ids)
            return queryset.filter(Q(id__in=ids_list))


@admin.register(User)
class UserAdmin(ExportMixin, admin.ModelAdmin):
    actions = [
        "deactivate_users",
        "wipe_user_data",
        "validate_apple_receipt",
        "reset_passwords_and_rotate_tokens",
        "bulk_edit",
    ]
    list_display = (
        'id',
        'name',
        'email',
        'artist_name',
        'category',
        'subscription_tier',
        'has_locked_splits',
        'comments',
    )
    list_display_links = ('id', 'name', 'email')
    form = UserForm
    ordering = ('is_staff', '-id')
    inlines = [CommentsInline, UserArtistRoleInline, UserMetadataInline]
    search_fields = ('=id', 'first_name', 'last_name', 'artist_name', '=email')
    readonly_fields = (
        'tollgate_releases',
        'transactions',
        'auth_token',
        'subscription_tier',
        'is_free_trial_active',
        'is_free_trial_eligible',
        'has_locked_splits',
        'subscription_link',
        'has_hyperwallet_account',
        'hyperwallet_payee_profile',
    )
    list_filter = [HasAppleReceipt, UserIDFilter]

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def subscription_link(self, obj):
        """Returns link to users newest subscription if there is one."""
        subscription_count = obj.subscriptions.count()
        subscription_url = reverse('admin:subscriptions_subscription_changelist')
        query_params = urlencode({'q': obj.email})
        subscription_url = f'{subscription_url}?{query_params}'
        return mark_safe(
            f'<a href="{subscription_url}">{subscription_count} Subscriptions</a>'
        )

    subscription_link.allow_tags = True
    subscription_link.short_description = "Subscriptions"

    def has_hyperwallet_account(self, obj):
        return obj.payee_profile_exist

    has_hyperwallet_account.boolean = True

    def hyperwallet_payee_profile(self, obj):
        if obj.payee_profile_exist:
            url = reverse('admin:payouts_payee_change', args=(obj.pk,))
            return mark_safe(f'<a href="{url}"> Hyperwallet Payee Profile</a>')
        return "-"

    def reset_passwords_and_rotate_tokens(self, request, qs):
        for user in qs:
            user.set_unusable_password()
            user.save()
            send_password_reset(user, urlconf="amuse.urls.app")

        token_qs = Token.objects.filter(user_id__in=qs.values_list("id", flat=True))
        rotate_auth_token(token_qs)

    reset_passwords_and_rotate_tokens.short_description = (
        "Reset passwords and rotate tokens"
    )

    def is_free_trial_active(self, obj):
        return obj.is_free_trial_active()

    is_free_trial_active.boolean = True

    def is_free_trial_eligible(self, obj):
        return obj.is_free_trial_eligible()

    is_free_trial_eligible.boolean = True

    def deactivate_users(self, request, qs):
        if "post" in request.POST and request.POST["post"] == "yes":
            qs.update(is_active=False)
            self.message_user(request, f"{qs.count()} users were deactivated.")
            return HttpResponseRedirect(request.get_full_path())

        return render(
            request,
            "admin/users/user/deactivate_intermediate.html",
            context={
                **self.admin_site.each_context(request),
                "title": "Are you sure?",
                "media": self.media,
                "opts": self.model._meta,
                "objects": qs.all(),
            },
        )

    deactivate_users.short_description = "Deactivate selected users"

    def wipe_user_data(self, request, qs):
        if qs and request.POST.get("post") == "yes":
            success_count = 0
            request_count = len(qs)

            for user_id in qs:
                result = launch_gdpr_tasks(user=user_id, initiator=request.user)

                if not result:
                    self.message_user(
                        request,
                        f"Failed to wipe data for user ({user_id}), updating user in active ffwd deal not allowed.",
                        messages.ERROR,
                    )
                else:
                    success_count += 1

            if success_count == request_count:
                message_status = messages.SUCCESS
                message = (f"GDPR cleanup initiated for {success_count} user(s).",)
            else:
                message_status = messages.WARNING
                message = f"GDPR cleanup initiated for {success_count} user(s). Failed to initiate for {request_count - success_count} user(s)."

            self.message_user(request, message, message_status)
            return HttpResponseRedirect(
                reverse("admin:users_gdprremovalrequest_changelist")
            )

        return render(
            request,
            "admin/users/user/wipe_user_data_gdpr.html",
            context={
                **self.admin_site.each_context(request),
                "title": "Warning! This action is irreversible!",
                "media": self.media,
                "opts": self.model._meta,
                "objects": qs.all(),
            },
        )

    wipe_user_data.short_description = "GDPR Cleanup & Deactivate User"

    def validate_apple_receipt(self, request, qs):
        users_with_receipts = qs.select_related('usermetadata').exclude(
            Q(usermetadata__apple_receipt="") | Q(usermetadata=None)
        )
        count = users_with_receipts.count()

        if request.method == 'POST' and request.POST.get('confirm', '') == 'yes':
            success_count = 0
            fail_count = 0
            dummy_request = copy(request)
            for user in users_with_receipts:
                dummy_request.user = user
                serializer = AppleSubscriptionSerializer(
                    data={'receipt_data': user.usermetadata.apple_receipt},
                    context={'request': dummy_request},
                )
                if serializer.is_valid():
                    serializer.save()
                    user.usermetadata.apple_receipt = ''
                    user.usermetadata.save()
                    success_count += 1
                else:
                    logger.info(
                        'admin validate apple receipt fail user: %s, errors: %s',
                        user.pk,
                        serializer.errors,
                    )
                    fail_count += 1

            self.message_user(
                request,
                f'{count} users had Apple receipt re-sent. succeeded: {success_count}, failed: {fail_count}',
            )
            return HttpResponseRedirect(request.get_full_path())

        return render(
            request,
            'admin/users/user/validate_apple_receipt.html',
            context={
                **self.admin_site.each_context(request),
                'title': f'Verify {count} receipts using Apple endpoint?',
                'media': self.media,
                'opts': self.model._meta,
                'users': users_with_receipts,
            },
        )

    validate_apple_receipt.short_description = "Verify Apple in-app Purchase"

    def bulk_edit(self, request, qs):
        step = int(request.POST.get('step', 0))
        form_class = BulkEditUserForm
        max_users = settings.BULK_EDIT_MAX_USERS

        if qs.count() > max_users:
            self.message_user(
                request,
                f"The maximum number of Users that can be edited with bulk edit action is {max_users}",
                messages.WARNING,
            )
            return HttpResponseRedirect(request.get_full_path())

        form = None
        if "post" in request.POST and step == 1:
            form = form_class(request.POST)
            if form.is_valid():
                form.bulk_update(request, qs)

                self.message_user(
                    request, f"Updated {qs.count()} users.", messages.SUCCESS
                )

                return HttpResponseRedirect(request.get_full_path())

        form = form or form_class()
        return render(
            request,
            'admin/users/bulk_edit/bulk_edit_form.html',
            context={
                **self.admin_site.each_context(request),
                'form': form,
                'title': f'Bulk Edit Users',
                'media': self.media,
                'opts': self.model._meta,
                'objects': qs.all(),
                'step': 1,
            },
        )

    def get_urls(self):
        urls = super().get_urls()
        urls = [
            path(
                '<path:object_id>/delete-hyperwallet-user-token/',
                self.admin_site.admin_view(self.delete_hyperwallet_user_token),
                name='users_delete_hyperwallet_user_token',
            ),
            path(
                '<path:object_id>/gdpr-wipe-user-data/',
                self.admin_site.admin_view(self.gdpr_wipe_user),
                name='gdpr_wipe_user_data',
            ),
        ] + urls

        return urls

    def tollgate_releases(self, user):
        url = reverse('admin:contenttollgate_genericrelease_changelist')
        release_count = user.releases.all().count()
        link = '<a href="%s?user_id=%s">%s releases</a>' % (url, user.id, release_count)
        return mark_safe(link)

    def transactions(self, user):
        url = reverse('admin:users_transaction_changelist')
        transactions_count = user.transactions.all().count()
        link = (
            f'<a href="{url}?user_id={user.pk}">{transactions_count} transactions</a>'
        )
        return mark_safe(link)

    def get_resource_class(self):
        return UserResource

    def gdpr_wipe_user(self, request, object_id):
        object_id = int(object_id)
        user = User.objects.get(pk=object_id)

        return render(
            request,
            "admin/users/user/wipe_user_data_gdpr.html",
            context={
                **self.admin_site.each_context(request),
                "title": "Warning! This action is irreversible!",
                "media": self.media,
                "opts": self.model._meta,
                "objects": [user],
            },
        )

    def delete_hyperwallet_user_token(self, request, object_id):
        object_id = int(object_id)
        user = User.objects.get(pk=object_id)
        redirect_url = reverse('admin:users_user_change', args=(object_id,))

        if not hasattr(user, 'usermetadata'):
            return HttpResponseServerError()

        usermetadata = user.usermetadata

        if request.method == 'POST' and request.POST.get('confirm') == "yes":
            usermetadata.hyperwallet_user_token = None
            usermetadata.save()
            return HttpResponseRedirect(redirect_url)

        context = {
            **self.admin_site.each_context(request),
            'media': self.media,
            'opts': self.model._meta,
            'user': user,
            'hyperwallet_user_token': usermetadata.hyperwallet_user_token,
            'redirect_url': redirect_url,
        }

        return TemplateResponse(
            request, "admin/users/user/delete_hyperwallet_user_token.html", context
        )

    def save_model(self, request, obj, form, change):
        if 'is_frozen' in form.changed_data and obj.is_frozen:
            user_frozen(obj)
            obj.disable_subscription()

        super(UserAdmin, self).save_model(request, obj, form, change)


class TransactionWithdrawalForm(forms.ModelForm):
    identification_number = forms.CharField(required=False)

    class Meta:
        model = TransactionWithdrawal
        fields = '__all__'


class TransactionWithdrawalInline(admin.StackedInline):
    model = TransactionWithdrawal
    form = TransactionWithdrawalForm
    extra = 0
    can_delete = False
    readonly_fields = (
        'payee_type',
        'name',
        'identification_number',
        'address',
        'country',
        'email',
        'phone',
        'verified',
        'has_hyperwallet_payment_token',
    )
    exclude = ('hyperwallet_payment_token',)

    def has_hyperwallet_payment_token(self, obj):
        if obj.hyperwallet_payment_token is not None:
            return True
        else:
            return False

    has_hyperwallet_payment_token.short_description = 'Is a Hyperwallet Payment'
    has_hyperwallet_payment_token.boolean = True


class TransactionDepositInline(admin.TabularInline):
    model = TransactionDeposit
    extra = 0
    can_delete = False
    fields = ('amount', 'isrc')
    readonly_fields = ('amount', 'isrc')


class TransactionInline(admin.TabularInline):
    model = LegacyRoyaltyAdvance.transactions.through
    extra = 0
    can_delete = False
    fields = (
        "transaction_link",
        "transaction_type",
        "transaction_amount",
        "transaction_status",
        "transaction_name",
        "transaction_artist_name",
        "transaction_created",
    )
    readonly_fields = (
        "transaction_link",
        "transaction_type",
        "transaction_amount",
        "transaction_status",
        "transaction_name",
        "transaction_artist_name",
        "transaction_created",
    )

    def transaction_link(self, obj):
        return mark_safe(
            '<a href="%s" target="_blank">Open transaction in new window</a>'
            % reverse('admin:users_transaction_change', args=[obj.transaction.id])
        )

    def transaction_type(self, obj):
        return dict(Transaction.TYPE_CHOICES).get(
            Transaction.objects.get(pk=obj.transaction.id).type
        )

    def transaction_status(self, obj):
        return dict(Transaction.STATUS_CHOICES).get(
            Transaction.objects.get(pk=obj.transaction.id).status
        )

    def transaction_amount(self, obj):
        return Transaction.objects.get(pk=obj.transaction.id).amount

    def transaction_name(self, obj):
        return Transaction.objects.get(pk=obj.transaction.id).user.name

    def transaction_artist_name(self, obj):
        return Transaction.objects.get(pk=obj.transaction.id).user.artist_name

    def transaction_created(self, obj):
        return Transaction.objects.get(pk=obj.transaction.id).created

    transaction_link.short_description = 'Link'
    transaction_type.short_description = 'Type'
    transaction_status.short_description = 'Status'
    transaction_amount.short_description = 'Amount'
    transaction_name.short_description = 'Name'
    transaction_artist_name.short_description = 'Artist'
    transaction_created.short_description = 'Created'


@admin.register(Transaction)
class AdminTransaction(admin.ModelAdmin):
    list_filter = ('type', 'status', 'user__category')
    list_display = (
        'type',
        'status',
        'amount',
        'transaction_withdrawal_verification',
        'hyperwallet_payment_token',
        'date',
        'user',
        'user_artist_name',
        'transaction_user_category',
        'created',
    )
    list_select_related = ('user',)
    search_fields = (
        '=user__id',
        'user__first_name',
        'user__last_name',
        'user__artist_name',
    )
    ordering = ('-id',)
    raw_id_fields = ('user',)
    inlines = (TransactionWithdrawalInline, TransactionDepositInline)

    def user_artist_name(self, obj):
        return obj.user.artist_name

    def transaction_user_category(self, obj):
        return obj.user.get_category_display()

    transaction_user_category.short_description = 'User Category'

    def transaction_withdrawal_verification(self, obj):
        if obj.withdrawal:
            return obj.withdrawal.verified

    transaction_withdrawal_verification.short_description = 'Verified'
    transaction_withdrawal_verification.boolean = True

    def hyperwallet_payment_token(self, obj):
        if (
            hasattr(obj, 'withdrawal')
            and obj.withdrawal.hyperwallet_payment_token is not None
        ):
            return True
        else:
            return False

    hyperwallet_payment_token.short_description = 'Is a Hyperwallet Payment'
    hyperwallet_payment_token.boolean = True


@admin.register(TransactionSource)
class AdminTransactionSources(admin.ModelAdmin):
    list_display = ('name', 'store_name')

    def get_queryset(self, request):
        return TransactionSource.objects.all()

    def store_name(self, obj):
        return obj.store.name if obj.store else '-'


@admin.register(TransactionFile)
class AdminTransactionFile(admin.ModelAdmin):
    ordering = ('-id',)
    list_display = ('type', 'status', 'date')
    readonly_fields = ('status',)


class HasOwnerListFilter(admin.SimpleListFilter):
    title = 'Has owner'
    parameter_name = 'has_owner'

    def lookups(self, request, model_admin):
        return (('yes', 'Yes'), ('no', 'No'))

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(owner__isnull=False).distinct()

        if self.value() == 'no':
            return queryset.filter(owner__isnull=True).distinct()


class HasReleasesListFilter(admin.SimpleListFilter):
    title = 'Has Releases'
    parameter_name = 'has_releases'

    def lookups(self, request, model_admin):
        return (('yes', 'Yes'), ('no', 'No'))

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(releaseartistrole__isnull=False).distinct()

        if self.value() == 'no':
            return queryset.filter(releaseartistrole__isnull=True).distinct()


class IsSongContributorListFilter(admin.SimpleListFilter):
    title = 'Has Song Contribution'
    parameter_name = 'is_song_contributor'

    def lookups(self, request, model_admin):
        return (('yes', 'Yes'), ('no', 'No'))

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(songartistrole__isnull=False).distinct()

        if self.value() == 'no':
            return queryset.filter(songartistrole__isnull=True).distinct()


class ArtistV2Form(ModelForm):
    tiktok_name = forms.CharField(
        validators=[validate_tiktok_name],
        required=False,
        help_text='Tiktok username without @',
    )

    class Meta:
        model = ArtistV2
        fields = '__all__'

    def clean_twitter_name(self):
        return self.cleaned_data['twitter_name'] or None

    def clean_facebook_page(self):
        return self.cleaned_data['facebook_page'] or None

    def clean_instagram_name(self):
        return self.cleaned_data['instagram_name'] or None

    def clean_tiktok_name(self):
        return self.cleaned_data['tiktok_name'] or None

    def clean_soundcloud_page(self):
        return self.cleaned_data['soundcloud_page'] or None

    def clean_youtube_channel(self):
        return self.cleaned_data['youtube_channel'] or None

    def clean_apple_id(self):
        return self.cleaned_data['apple_id'] or None

    def clean_spotify_id(self):
        return self.cleaned_data['spotify_id'] or None


class ArtistV2Filter(InputFilter):
    parameter_name = 'artist'
    title = 'Artists IDs'

    def queryset(self, request, queryset):
        if self.value():
            ids = self.value()
            ids_list = parse_input_string_to_digits(ids)
            return queryset.filter(Q(id__in=ids_list))


@admin.register(ArtistV2)
class ArtistV2Admin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'owner_link',
        'tollgate_releases',
        'created',
        'updated',
    )
    list_filter = (
        ArtistV2Filter,
        HasOwnerListFilter,
        HasReleasesListFilter,
        IsSongContributorListFilter,
    )

    form = ArtistV2Form
    search_fields = ('=id', 'name', 'owner__id', 'spotify_id')
    fields = (
        'name',
        'owner',
        'image',
        'spotify_page',
        'twitter_name',
        'facebook_page',
        'instagram_name',
        'tiktok_name',
        'soundcloud_page',
        'youtube_channel',
        'apple_id',
        'spotify_id',
        'spotify_for_artists_url',
        'audiomack_id',
        'tollgate_releases',
        'created',
        'updated',
    )
    readonly_fields = (
        'tollgate_releases',
        'created',
        'updated',
        'spotify_for_artists_url',
        'audiomack_id',
    )
    exclude = ('audiomack_access_token', 'audiomack_access_token_secret')
    raw_id_fields = ('owner',)
    inlines = (UserArtistRoleInline,)
    actions = ('remove_s4a_url',)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def tollgate_releases(self, artist):
        if not artist.id:
            return '-'

        url = reverse('admin:contenttollgate_genericrelease_changelist')
        release_count = Release.objects.filter(
            id__in=ReleaseArtistRole.objects.filter(artist_id=artist.id)
            .values('release')
            .union(
                SongArtistRole.objects.filter(artist_id=artist.id).values(
                    'song__release'
                )
            )
        ).count()

        link = '<a href="%s?artist_id=%s">%s releases</a>' % (
            url,
            artist.id,
            release_count,
        )
        return mark_safe(link)

    def owner_link(self, item):
        if not item.owner:
            return "-"

        user_url = reverse('admin:users_user_change', args=(item.owner.id,))
        user_link = '<a href="%s">%s</a>' % (user_url, item.owner.name)

        return mark_safe(user_link)

    owner_link.short_description = "Owner"

    def remove_s4a_url(self, request, queryset):
        artist_names = ', '.join(queryset.values_list('name', flat=True))
        if request.POST and request.POST.get('confirm') == 'yes':
            queryset.update(spotify_for_artists_url=None)
            messages.success(
                request, f'Spotify for artists URL removed for {artist_names}'
            )
        else:
            return TemplateResponse(
                request,
                'admin/confirm.html',
                {
                    **self.admin_site.each_context(request),
                    'action': 'remove_s4a_url',
                    'confirm_message': f'remove S4A URL for artist(s) {artist_names}',
                    'queryset': queryset,
                },
            )

    remove_s4a_url.short_description = "Remove S4A URL"


class StatusFilter(admin.SimpleListFilter):
    title = 'Payment Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (("PENDING", "PENDING"), ("COMPLETED", "COMPLETED"))

    def queryset(self, request, queryset):
        ids = []
        if self.value() == 'PENDING':
            for item in queryset:
                if item.transactions.filter(status=Transaction.STATUS_PENDING).exists():
                    ids.append(item.id)
            return queryset.filter(id__in=ids)
        if self.value() == 'COMPLETED':
            for item in queryset:
                if item.transactions.filter(status=Transaction.STATUS_PENDING).exists():
                    ids.append(item.id)
            return queryset.exclude(id__in=ids)


@admin.register(LegacyRoyaltyAdvance)
class LegacyRoyaltyAdvanceAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'user_artist_name',
        'status',
        'label',
        'date_start',
        'date_end',
        'date_updated',
    )
    list_filter = ('status', 'label', StatusFilter)
    raw_id_fields = ('user',)
    readonly_fields = ('address', 'email', 'identification_number')
    inlines = (TransactionInline,)
    exclude = ("transactions",)

    def user_artist_name(self, obj):
        return obj.user.artist_name


@admin.register(UserGDPR)
class UserGDPRAdmin(admin.ModelAdmin):
    list_display = (
        'initiator',
        'user_id',
        'zendesk_data',
        'segment_data',
        'fuga_data',
        'is_done',
    )

    readonly_fields = [
        'initiator',
        'user',
        'user_id',
        'minfraud_entries',
        'artist_v2_history_entries',
        'user_history_entries',
        'email_adress',
        'user_first_name',
        'user_last_name',
        'user_social_links',
        'user_artist_name',
        'artist_v2_names',
        'artist_v2_social_links',
        'artist_v1_names',
        'artist_v1_social_links',
        'user_apple_signin_id',
        'user_facebook_id',
        'user_firebase_token',
        'user_zendesk_id',
        'transaction_withdrawals',
        'user_isactive_deactivation',
        'user_newsletter_deactivation',
        'zendesk_data',
        'segment_data',
        'fuga_data',
    ]

    def initiator(self, obj):
        return obj.initiator.name

    def is_done(self, obj):
        return UserGDPR.check_done(user_id=obj.user_id)


class GDPRRemovalRequest(User):
    class Meta:
        proxy = True
        verbose_name = 'GDPR Removal Request'
        verbose_name_plural = 'GDPR Removal Requests'


@admin.register(GDPRRemovalRequest)
class GDPRRemovalRequests(admin.ModelAdmin):
    actions = ["reject_removal_request", "wipe_user_data"]

    list_display = (
        'user_link',
        'email',
        'category',
        'subscription_tier',
        'delete_requested_at',
        'comments',
    )

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def get_queryset(self, *args, **kwargs):
        return (
            User.objects.filter(usermetadata__is_delete_requested=True)
            .exclude(id__in=UserGDPR.objects.values('user_id'))
            .order_by('-usermetadata__delete_requested_at')
        )

    def has_add_permission(self, request, obj=None):
        return False

    def delete_requested_at(self, obj):
        if hasattr(obj, 'usermetadata'):
            return obj.usermetadata.delete_requested_at
        return ""

    def reject_removal_request(self, request, qs):
        UserMetadata.objects.filter(user__in=qs).update(is_delete_requested=False)

    reject_removal_request.short_description = "Reject GDPR Removal Request"

    @mark_safe
    def user_link(self, obj):
        return f'<a href="{reverse(f"admin:users_user_change", args=[obj.id])}"><b>{obj.id}</b></a>'

    user_link.allow_tags = True
    user_link.short_description = 'User'

    def wipe_user_data(self, request, qs):
        return render(
            request,
            "admin/users/user/wipe_user_data_gdpr.html",
            context={
                **self.admin_site.each_context(request),
                "title": "Warning! This action is irreversible!",
                "media": self.media,
                "opts": self.model._meta,
                "objects": qs.all(),
            },
        )

    wipe_user_data.short_description = "GDPR Cleanup & Deactivate User"


class RoyaltyInvitationsStatusFilter(admin.SimpleListFilter):
    title = 'Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return RoyaltyInvitation.STATUS_CHOICES

    def queryset(self, request, queryset):
        status = self.value()

        if status is not None:
            return queryset.filter(status=status)

        return queryset


class RoyaltyInvitationsReleaseIDFilter(InputFilter):
    parameter_name = 'release_id'
    title = 'Release IDs'

    def queryset(self, request, queryset):
        if self.value() is not None:
            ids = self.value()
            ids_list = parse_input_string_to_digits(ids)
            return queryset.filter(Q(royalty_split__song__release__id__in=ids_list))


class RoyaltyInvitationsSongIDFilter(InputFilter):
    parameter_name = 'song_id'
    title = 'Song IDs'

    def queryset(self, request, queryset):
        if self.value() is not None:
            ids = self.value()
            ids_list = parse_input_string_to_digits(ids)
            return queryset.filter(Q(royalty_split__song__id__in=ids_list))


class RoyaltyInvitationsReleaseIDFilter(InputFilter):
    parameter_name = 'release_id'
    title = 'Release IDs'

    def queryset(self, request, queryset):
        if self.value() is not None:
            ids = self.value()
            ids_list = parse_input_string_to_digits(ids)
            return queryset.filter(Q(royalty_split__song__release__id__in=ids_list))


class RoyaltyInvitationsSplitIDFilter(InputFilter):
    parameter_name = 'split_id'
    title = 'Split IDs'

    def queryset(self, request, queryset):
        if self.value() is not None:
            ids = self.value()
            ids_list = parse_input_string_to_digits(ids)
            return queryset.filter(Q(royalty_split__id__in=ids_list))


@admin.register(RoyaltyInvitation)
class AdminRoyaltyInvitation(admin.ModelAdmin):
    list_filter = (
        RoyaltyInvitationsStatusFilter,
        RoyaltyInvitationsReleaseIDFilter,
        RoyaltyInvitationsSongIDFilter,
        RoyaltyInvitationsSplitIDFilter,
    )
    actions = ['action_resend_royalty_invitations', 'action_change_status_to_decline']
    list_display = (
        'id',
        'get_royalty_split',
        'song_id',
        'song_name',
        'release_id',
        'get_inviter',
        'get_invitee',
        'status',
        'email',
        'phone_number',
        'last_sent',
        'created',
        'get_expiration_time',
    )
    readonly_fields = (
        'royalty_split',
        'song_id',
        'song_name',
        'release_id',
        'token',
        'inviter',
        'invitee',
        'status',
        'email',
        'phone_number',
        'name',
        'last_sent',
        'created',
        'updated',
        'expiration_time',
    )
    search_fields = (
        'royalty_split__song__id',
        'royalty_split__song__release__id',
        'royalty_split__id',
        'inviter__id',
        'invitee__id',
        'email',
        'phone_number',
        'name',
    )
    ordering = (
        '-created',
        'inviter',
        'invitee',
    )

    raw_id_fields = ('royalty_split', 'inviter', 'invitee')

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                'royalty_split',
                'inviter',
                'invitee',
                'royalty_split__song',
                'royalty_split__song__release',
            )
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def get_royalty_split(self, obj):
        return mark_safe(
            f'<a href="%s"">{obj.royalty_split_id}</a>'
            % reverse("admin:releases_royaltysplit_change", args=[obj.royalty_split_id])
        )

    get_royalty_split.short_description = 'Split ID'

    def song_id(self, obj):
        return mark_safe(
            f'<a href="%s"">{obj.royalty_split.song_id}</a>'
            % reverse("admin:releases_song_change", args=[obj.royalty_split.song_id])
        )

    def release_id(self, obj):
        return mark_safe(
            f'<a href="%s"">{obj.royalty_split.song.release_id}</a>'
            % reverse(
                "admin:releases_release_change",
                args=[obj.royalty_split.song.release_id],
            )
        )

    def song_name(self, obj):
        return mark_safe(
            f'<a href="%s"">{obj.royalty_split.song.name}</a>'
            % reverse(
                "admin:releases_release_change",
                args=[obj.royalty_split.song.name],
            )
        )

    def get_inviter(self, obj):
        return mark_safe(
            f'<a href="%s"">{obj.inviter}</a>'
            % reverse("admin:users_user_change", args=[obj.inviter_id])
        )

    get_inviter.short_description = 'Inviter'

    def get_invitee(self, obj):
        if obj.invitee is not None:
            return mark_safe(
                f'<a href="%s"">{obj.invitee}</a>'
                % reverse("admin:users_user_change", args=[obj.invitee_id])
            )

        return obj.name

    get_invitee.short_description = 'Invitee'

    def get_expiration_time(self, obj):
        if obj.status == RoyaltyInvitation.STATUS_PENDING:
            return obj.expiration_time
        return '-'

    get_expiration_time.short_description = 'Expire at'

    def action_resend_royalty_invitations(self, request, queryset):
        lst = queryset.filter(status=RoyaltyInvitation.STATUS_PENDING).all()
        for item in lst:
            send_royalty_invite(item, item.royalty_split, item.token)

    action_resend_royalty_invitations.short_description = (
        'Resend selected royalty invitations [PENDING only]'
    )

    def action_change_status_to_decline(self, request, queryset):
        queryset.filter(
            status__in=[
                RoyaltyInvitation.STATUS_CREATED,
                RoyaltyInvitation.STATUS_PENDING,
            ]
        ).update(status=RoyaltyInvitation.STATUS_DECLINED)

    action_change_status_to_decline.short_description = (
        'Decline selected royalty invitations [PENDING and CREATED only]'
    )


def rotate_auth_token(token_qs):
    for item in token_qs:
        Token.objects.filter(pk=item.pk).update(
            key=binascii.hexlify(os.urandom(20)).decode()
        )
