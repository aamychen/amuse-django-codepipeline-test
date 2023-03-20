from decimal import ROUND_HALF_UP, Decimal

from amuse.vendor.currencylayer import CurrencyLayer
from amuse.vendor.exchangeratehost import ExchangeRateHost
from countries.models import Country

CURRENCY_SEK = 'SEK'
exchangerate_client = ExchangeRateHost()
currencylayer_client = CurrencyLayer()


def calculate_vat(
    country: Country, currency_code: str, amount: Decimal
) -> (Decimal, Decimal):
    vat_amount = country.vat_amount(amount)

    if currency_code == CURRENCY_SEK:
        return vat_amount, vat_amount

    if vat_amount == 0:
        return vat_amount, vat_amount

    vat_amount_sek = currencylayer_client.convert(
        from_currency=currency_code, to_currency=CURRENCY_SEK, amount=vat_amount
    )

    if vat_amount_sek is None:
        vat_amount_sek = exchangerate_client.convert(
            from_currency=currency_code, to_currency=CURRENCY_SEK, amount=vat_amount
        )

    if vat_amount_sek:
        vat_amount_sek = vat_amount_sek.quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    return vat_amount, vat_amount_sek
