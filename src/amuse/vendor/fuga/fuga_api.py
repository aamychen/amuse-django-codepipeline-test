import requests

from django.conf import settings
from django.core.cache import cache


# Cache Fuga token for 1h

CACHE_PERIOD_IN_SECONDS = 1 * 60 * 60


class FugaNotFoundError(Exception):
    pass


class FugaAPIClient:
    def __init__(self):
        self.base_url = settings.FUGA_API_URL
        self.cache_key = settings.FUGA_API_CACHE_COOKIE_KEY
        self.cookie = None

    def _get_cookie(self):
        if not self.cookie:
            self.cookie = cache.get(self.cache_key)
        if not self.cookie:
            self._login()
        return self.cookie

    def _login(self):
        if self.base_url == "https://example.com":
            self.cookie = None
            return

        payload = {
            "name": settings.FUGA_API_USER,
            "password": settings.FUGA_API_PASSWORD,
        }
        r = requests.post(self.base_url + "login", data=payload)

        if r.status_code == 200:
            auth_token = r.headers["Set-Cookie"].split(";")[0].split("=")[1]
            self.cookie = {"connect.sid": auth_token}
            cache.set(self.cache_key, self.cookie, CACHE_PERIOD_IN_SECONDS)
        else:
            raise ConnectionError(r.__dict__)

    def _request(self, method, url, retries=0, **kwargs):
        if self.base_url == "https://example.com":
            self.cookie = None
            return
        req = requests.request(method, url, cookies=self._get_cookie(), **kwargs)
        if req.status_code == 200:
            if method == "DELETE":
                return {}
            return req.json()

        if req.status_code == 401:
            if retries < 3:
                self._login()
                return self._request(method, url, retries=retries + 1, **kwargs)
        if req.status_code == 404:
            raise FugaNotFoundError()
        raise ConnectionError(req.__dict__)

    def get_fuga_product_id(self, upc):
        url = self.base_url + "v2/products/?search=%s" % upc
        data = self._request("GET", url)
        return data["product"][0]["id"] if data and data["product"] else None

    def get_delivery_instructions(self, fuga_product_id):
        url = self.base_url + "v1/products/%s/delivery_instructions" % fuga_product_id
        return self._request("GET", url)

    def get_delivery_history_for_dsp(self, fuga_product_id, dsp_id):
        url = self.base_url + "v2/products/%s/delivery_instructions/%s/history" % (
            fuga_product_id,
            dsp_id,
        )
        return self._request("GET", url)

    def get_delivery_history(self, upc=None, fuga_product_id=None):
        if upc:
            fuga_product_id = self.get_fuga_product_id(upc)
        if not fuga_product_id:
            return {}
        data = self.get_delivery_instructions(fuga_product_id)
        delivery_history = {}
        for item in data["delivery_instructions"]:
            delivery_history[item["dsp"]["id"]] = {
                "lead_time": item["lead_time"],
                "state": item["state"],
                "action": item["action"],
            }
        return delivery_history

    def get_product(self, fuga_product_id):
        url = self.base_url + "v2/products/%s" % fuga_product_id
        data = self._request("GET", url)
        return data

    def get_product_status(self, fuga_product_id):
        data = self.get_product(fuga_product_id)
        status = 'PUBLISHED' if data["state"] == 'DELIVERED' else data["state"]
        return status

    def get_product_assets(self, fuga_product_id):
        url = self.base_url + "v2/products/%s/assets" % fuga_product_id
        data = self._request("GET", url)
        return data

    def delete_product(self, fuga_product_id, delete_assets=True):
        '''
        This function deletes a product/release from Fuga and takes down
        the release to previously delivered DSPs by Fuga. If delete_assets=True it also
        deletes the assets if they are not attached to another Fuga product/release.
        '''

        url = self.base_url + "v2/products/%s" % fuga_product_id
        if delete_assets:
            url += "?delete_assets=true"
        try:
            self._request("DELETE", url)
        except ConnectionError:
            return False
        return True

    def get_artist_identifier(self, fuga_artist_id):
        url = self.base_url + "v2/artists/%s/identifier" % fuga_artist_id
        data = self._request("GET", url)
        return data

    def post_product_deliver(self, fuga_product_id, fuga_store_ids):
        url = (
            self.base_url
            + "v2/products/%s/delivery_instructions/deliver" % fuga_product_id
        )
        fuga_stores = [{"dsp": fuga_store_id} for fuga_store_id in fuga_store_ids]
        data = self._request("POST", url, json=fuga_stores)
        return data

    def post_product_takedown(self, fuga_product_id, fuga_store_ids):
        url = (
            self.base_url
            + "v2/products/%s/delivery_instructions/takedown" % fuga_product_id
        )
        fuga_stores = [{"dsp": fuga_store_id} for fuga_store_id in fuga_store_ids]
        data = self._request("POST", url, json=fuga_stores)
        return data
