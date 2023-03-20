from functools import reduce
from typing import List, Optional, Union

from .models import Country


class CountryCodec(object):
    @staticmethod
    def encode(countries: Optional[Union[Country, List[Country]]]):
        if not countries:
            return 0

        if not isinstance(countries, list):
            countries = [countries]

        return reduce(lambda x, y: x + 2**y.internal_numeric_code, countries, 0)

    @staticmethod
    def decode(code: int):
        countries = list(Country.objects.all())
        result = [
            country
            for country in countries
            if (code & (2**country.internal_numeric_code)) > 0
        ]

        return result
