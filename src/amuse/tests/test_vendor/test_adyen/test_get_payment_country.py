import responses

from amuse.tests.test_vendor.test_adyen.base import AdyenBaseTestCase
from amuse.tests.test_vendor.test_adyen.helpers import mock_payment_details
from amuse.vendor.adyen import get_payment_country
from amuse.vendor.adyen.exceptions import IssuerCountryAPIError
from countries.tests.factories import CountryFactory


class TestGetPaymentCountry(AdyenBaseTestCase):
    def setUp(self):
        CountryFactory(code='SE')
        self.country = CountryFactory(code='US')

    @responses.activate
    def test_found(self):
        self._add_country_check_response(self.country.code)
        payment_country = get_payment_country(1, mock_payment_details())
        self.assertEqual(payment_country, self.country)

    @responses.activate
    def test_country_not_in_db_returns_none(self):
        self._add_country_check_response('nonexisting')
        self.assertIsNone(get_payment_country(1, mock_payment_details()))

    @responses.activate
    def test_unavailable_country_returns_none(self):
        self._add_country_check_response(None)
        self.assertIsNone(get_payment_country(1, mock_payment_details()))

    @responses.activate
    def test_adyen_api_error_raises_exception(self):
        self._add_country_check_response(
            response='{"status":422,"errorCode":"14_007","message":"Invalid payment method data","errorType":"validation"}',
            status_code=422,
        )

        with self.assertRaises(IssuerCountryAPIError):
            get_payment_country(1, mock_payment_details())
