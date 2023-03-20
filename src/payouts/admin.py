import json
from django.shortcuts import render
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Q
from payouts.models import (
    Payee,
    TransferMethod,
    Payment,
    Provider,
    TransferMethodConfiguration,
)
from artistmanager.admin import InputFilter
from artistmanager.utils import parse_input_string_to_digits
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory
from amuse.logging import logger


class TransferMethodInline(admin.TabularInline):
    model = TransferMethod
    list_display = (
        "payee",
        "external_id",
        "type",
        "status",
        "provider",
        "currency",
        "active",
        "created",
    )
    readonly_fields = ('created',)
    raw_id_fields = ("payee", "currency")
    extra = 0
    can_delete = False


class PaymentInline(admin.TabularInline):
    model = Payment
    list_display = (
        "payee",
        "external_id",
        "transfer_method",
        "currency",
        "amount",
        "status",
        "created",
        "revenue_system_id",
    )
    readonly_fields = ('created',)
    raw_id_fields = ("payee", "transfer_method", "currency")
    extra = 0
    can_delete = False


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "external_id",
        "active",
        "created",
    )
    readonly_fields = ('created',)

    def has_delete_permission(self, request, obj=None):
        # Disable delete
        return False


@admin.register(TransferMethod)
class TransferMethodAdmin(admin.ModelAdmin):
    list_display = (
        "payee",
        "external_id",
        "type",
        "status",
        "provider",
        "currency",
        "active",
        "created",
    )
    list_filter = (
        'status',
        'currency',
        'provider',
        'active',
    )
    readonly_fields = ('created',)
    raw_id_fields = ("payee", "currency")
    search_fields = ("external_id",)

    def has_delete_permission(self, request, obj=None):
        # Disable delete
        return False


class FilterByUserId(InputFilter):
    parameter_name = 'user'
    title = 'User ID'

    def queryset(self, request, queryset):
        if self.value():
            ids = self.value()
            ids_list = parse_input_string_to_digits(ids)
            return queryset.filter(Q(payee__user__id__in=ids_list))


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payee",
        "external_id",
        "transfer_method",
        "currency",
        "amount",
        "status",
        "payee_user",
        "created",
        "revenue_system_id",
    )
    list_filter = (FilterByUserId, 'status', 'payment_type')

    readonly_fields = ('created',)
    raw_id_fields = ("payee", "transfer_method", "currency")
    search_fields = ("external_id", "payee__user__email")

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        # Disable delete
        return False

    def payee_user(self, item):
        user_url = reverse('admin:users_user_change', args=(item.payee.user.id,))
        user_link = '<a href="%s">%s</a>' % (user_url, item.payee.user.id)
        return mark_safe(user_link)


@admin.register(Payee)
class PayeeAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "external_id",
        "status",
        "verification_status",
        "type",
        "provider",
        "created",
    )
    list_filter = (
        'status',
        'provider',
    )
    actions = ['display_user_receipt', 'remove_payee_data', 'display_user_profile']
    readonly_fields = ('created',)
    raw_id_fields = ("user",)
    search_fields = ("user__email", "external_id")
    inlines = (
        TransferMethodInline,
        PaymentInline,
    )

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        # Disable delete
        return False

    def display_user_receipt(self, request, qs):
        payee = qs.filter(status='PRE_ACTIVATED').first()
        try:
            client = HyperWalletEmbeddedClientFactory().create(payee.user.country)
            response = client.listReceiptsForUser(
                userToken=payee.external_id, params={'createdAfter': '2021-01-01'}
            )
            data = [r.asDict() for r in response]
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

    def remove_payee_data(self, request, qs):
        is_confirmed = (
            request.method == 'POST' and request.POST.get('confirm', '') == 'yes'
        )

        if not is_confirmed:
            return render(
                request,
                'payee_cleanup.html',
                context={
                    **self.admin_site.each_context(request),
                    'title': f'Delete Payee data',
                    'media': self.media,
                    'opts': self.model._meta,
                    'payees': qs,
                    'action_name': 'remove_payee_data',
                    'description': [
                        "This action will delete all Payee related data from system.",
                        "Payments and Transfer methods belonging to user will be also removed",
                    ],
                },
            )
        try:
            ids = [p.user_id for p in qs]
            for payee in qs:
                Payment.objects.filter(payee=payee).delete()
                TransferMethod.objects.filter(payee=payee).delete()
            qs.delete()
            logger.info(
                f"Pyees data have been removed ids={ids}. Issued by {request.user.email}"
            )
            self.message_user(
                request,
                f"Pyees data have been removed ids={ids}. Issued by {request.user.email}",
                messages.SUCCESS,
            )

        except Exception as e:
            self.message_user(request, f"{str(e)}.", messages.ERROR)

    def display_user_profile(self, request, qs):
        payee = qs.first()
        try:
            data = {}
            user_country = payee.user.country
            hw_client = HyperWalletEmbeddedClientFactory().create(
                country_code=user_country
            )
            user_data = hw_client.getUser(userToken=payee.external_id)
            trms = hw_client.listTransferMethods(userToken=payee.external_id)
            data['user_profile'] = user_data.asDict()
            data['trms'] = trms.asDict()
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


@admin.register(TransferMethodConfiguration)
class TransferMethodConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "currency",
        "type",
        "fee",
        "limits",
    )
    raw_id_fields = ("currency",)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        # Disable delete
        return False
