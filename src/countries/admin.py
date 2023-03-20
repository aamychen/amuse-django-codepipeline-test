from django.contrib import admin

from countries.models import Country, ExchangeRate, Currency


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'code',
        'region_code',
        'vat_percentage',
        'is_adyen_enabled',
        'is_signup_enabled',
    )


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('currency', 'year', 'quarter', 'rate')
    list_filter = ('year', 'quarter')
    search_fields = ('currency__code',)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'decimals')
    search_fields = ('code', 'name')
