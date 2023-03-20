import csv
import time
from datetime import datetime

from django.contrib import admin
from django.contrib import messages
from django.forms import Form, DateField, ChoiceField, RadioSelect
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path
from django.utils.safestring import mark_safe

from amuse.vendor.adyen.base import AdyenRefund
from payments.models import PaymentMethod, PaymentTransaction
from payments.reporting_utils import ReportingUtils
from .services.moss import MossReport, MossReportException
from .widgets import MonthYearWidget


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    actions = ['adyen_refund', 'export_to_csv']
    list_display = (
        'user',
        'email',
        'amount',
        'vat_amount',
        'currency',
        'created',
        'paid_until',
        'status',
        'provider',
        'country',
        'external_transaction_id',
        'external_url',
        'platform',
    )
    list_filter = (
        'subscription__provider',
        'status',
        'platform',
        'subscription__plan',
        'country',
    )
    list_select_related = ('user', 'subscription')
    search_fields = ('user__email', 'external_transaction_id')
    raw_id_fields = ('user', 'subscription', 'payment_method')

    def external_url(self, payment):
        external_url = payment.external_url()
        if external_url:
            return mark_safe(
                '<a href="%s" target="_blank">%s…</a>'
                % (external_url, payment.subscription.get_provider_display())
            )
        return ''

    def get_urls(self):
        urls = super().get_urls()
        url_name_base = f'{self.model._meta.app_label}_{self.model._meta.model_name}'
        url_name_replace = f'{url_name_base}_moss'

        urls = [path('moss', self.create_moss_report, name=url_name_replace)] + urls
        return urls

    def email(self, payment):
        return payment.user.email

    def adyen_refund(self, request, qs):
        payment = qs.first()
        refund_executor = AdyenRefund(payment)
        is_confirmed = (
            request.method == 'POST' and request.POST.get('confirm', '') == 'yes'
        )
        if not is_confirmed:
            return render(
                request,
                'adyen_refund_action.html',
                context={
                    **self.admin_site.each_context(request),
                    'title': f'Refund Adyen payment',
                    'media': self.media,
                    'opts': self.model._meta,
                    'payment': qs.first(),
                    'action_name': 'adyen_refund',
                    'description': [
                        "This action sends REFUND request to Adyen.",
                        "Adyen will send us notification once operations is completed on their side.",
                        "Based on notification status payment status will be changed..",
                        "If this is last payment for subscription, subscription will be expired.",
                    ],
                },
            )

        response = refund_executor.refund()
        if not response['is_success']:
            self.message_user(request, f"{response['response']}.", messages.ERROR)
        else:
            self.message_user(
                request,
                f"Refund request send to Adyen for external_transaction id {payment.external_transaction_id}. Subscription and payment status will be changed on receiving SUCCESS notification from Adyen.",
                messages.SUCCESS,
            )

    def export_to_csv(self, request, qs):
        meta = self.model._meta
        filtered_fields = [
            'id',
            'external_transaction_id',
            'customer_payment_payload',
            'external_payment_response',
            'payment_method',
            'updated',
            'user',
            'status',
            'type',
            'vat_amount',
        ]
        field_names = [
            field.name for field in meta.fields if field.name not in filtered_fields
        ]
        start_q = time.time()
        dateset = qs.filter(amount__gt=0).prefetch_related(
            'subscription', 'plan', 'currency', 'country'
        )
        result_list = list(dateset)
        end_q = time.time()

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(
            ReportingUtils.get_report_prefix()
        )
        writer = csv.writer(response)

        write_start = time.time()
        writer.writerow(field_names)
        for obj in result_list:
            writer.writerow(
                [ReportingUtils.data_formatter(obj, field) for field in field_names]
            )
        writer_end = time.time()

        self.message_user(
            request,
            f'Data exported total results {dateset.count()} DEBUG query_time={end_q - start_q} , write_time={writer_end - write_start}',
            messages.SUCCESS,
        )

        return response

    def create_moss_report(self, request):
        if request.method == 'POST':
            year = int(request.POST.get('period_year'))
            month = int(request.POST.get('period_month'))
            selected_country = int(request.POST.get('countries'))
            country = 'SE' if selected_country == MossCreteForm.COUNTRY_SWEDEN else None

            filename_suffix = 'SE' if country else 'ROW'
            filename = f'moss_{year}_{month}_{filename_suffix}.csv'
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename={filename}'

            try:
                MossReport(year, month, country=country).generate_report(response)
                return response
            except MossReportException as ex:
                self.message_user(request, message=str(ex), level=messages.ERROR)
                return HttpResponseRedirect(request.get_full_path())

        return render(
            request,
            'admin/payments/create_moss_report.html',
            context={
                **self.admin_site.each_context(request),
                'form': MossCreteForm(
                    initial={
                        'countries': MossCreteForm.COUNTRY_ROW,
                        'period': datetime.today().replace(day=1),
                    }
                ),
                'title': f'MOSS Report',
                'media': self.media,
                'opts': self.model._meta,
            },
        )


class MossCreteForm(Form):
    COUNTRY_SWEDEN = 0
    COUNTRY_ROW = 1

    COUNTRY_CHOICES = ((COUNTRY_SWEDEN, 'Sweden'), (COUNTRY_ROW, 'Rest of World'))

    period = DateField(
        required=True,
        widget=MonthYearWidget(years=range(2015, datetime.today().year + 2)),
    )

    countries = ChoiceField(choices=COUNTRY_CHOICES, widget=RadioSelect)


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'external_recurring_id',
        'method',
        'summary',
        'expiry_date',
        'created',
    )
    list_select_related = ('user',)
    raw_id_fields = ('user',)
    readonly_fields = (
        'created',
        'expiry_date',
        'external_recurring_id',
        'method',
        'summary',
        'updated',
        'user',
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields
        return []
