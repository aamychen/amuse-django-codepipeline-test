import json
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.core.cache import cache

CACHE_PERIOD_IN_SECONDS = 1 * 60 * 60


class SpotifyAtlasAPI:
    base_url = "https://atlas-view.spotify.com/"
    sonar_base_url = "https://sonar-view.spotify.com/"
    oauth_uri = "https://accounts.spotify.com/oauth2/v2/auth"
    api_token_uri = "https://accounts.spotify.com/api/token"
    redirect_uri = "https://musicproviders.spotify.com"
    cache_key = "spotify-cms-access-token"

    def __init__(self):
        self.in_production = False if settings.SPOTIFY_ATLAS_COOKIE is None else True
        self.cookie = {"sp_dc": settings.SPOTIFY_ATLAS_COOKIE}
        self.access_token = None

    @staticmethod
    def _extract_auth_code_from_html_response(html_text):
        for line in html_text.split("\n"):
            if "code" in line:
                line_with_auth_code = json.loads("{%s}" % line.strip()[:-1])
                return line_with_auth_code["code"]
        return None

    def _get_auth_code(self):
        if not self.in_production:
            return
        params = {
            "response_type": "code",
            "client_id": settings.SPOTIFY_ATLAS_AMUSE_CLIENT_ID,
            "scope": "openid profile email",
            "redirect_uri": self.redirect_uri,
            "code_challenge": settings.SPOTIFY_ATLAS_CODE_CHALLENGE,
            "code_challenge_method": "S256",
            "state": settings.SPOTIFY_ATLAS_STATE,
            "response_mode": "web_message",
            "prompt": "none",
        }
        res = requests.get(self.oauth_uri, cookies=self.cookie, params=params)
        if res.status_code == 200:
            # Return format is HTML that contains the auth_code
            return self._extract_auth_code_from_html_response(res.text)
        else:
            raise ConnectionError(res.__dict__)

    def _get_access_token_from_auth_code(self, auth_code):
        if not self.in_production:
            return
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.SPOTIFY_ATLAS_AMUSE_CLIENT_ID,
            "code": auth_code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": settings.SPOTIFY_ATLAS_CODE_VERIFIER,
        }
        res = requests.post(self.api_token_uri, data=data, headers=headers)
        if res.status_code == 200:
            return res.json().get("access_token")
        else:
            raise ConnectionError(res.__dict__)

    def _login(self):
        auth_code = self._get_auth_code()
        self.access_token = self._get_access_token_from_auth_code(auth_code)
        if self.access_token:
            cache.set(self.cache_key, self.access_token, CACHE_PERIOD_IN_SECONDS)

    def _get_access_token(self):
        if not self.access_token:
            self.access_token = cache.get(self.cache_key)
        if not self.access_token:
            self._login()
        return self.access_token

    def _request(self, method, url, retries=0, **kwargs):
        if not self.in_production:
            return
        headers = {"Authorization": "Bearer %s" % self._get_access_token()}
        req = requests.request(method, url, headers=headers, **kwargs)
        if req.status_code == 200:
            if method == "DELETE":
                return {}
            return req.json()

        if req.status_code == 401:
            if retries < 3:
                self._login()
                return self._request(method, url, retries=retries + 1, **kwargs)
        raise ConnectionError(req.__dict__)

    def search_album_by_upc(self, upc):
        url = self.base_url + "v3/search/album"
        params = {"searchTerm": upc}
        data = self._request("GET", url, params=params)
        return data["searchResults"]

    def get_album(self, album_spotify_id):
        url = self.base_url + "v2/album/%s" % album_spotify_id
        data = self._request("GET", url)
        return data

    def get_album_track(self, album_spotify_id, track_spotify_id):
        url = self.base_url + "v2/album/{}/track/{}".format(
            album_spotify_id, track_spotify_id
        )
        data = self._request("GET", url)
        return data

    def _sonar_search(
        self,
        search_term=None,
        from_date=None,
        to_date=None,
        show_errors=False,
        limit=10,
    ):
        url = self.sonar_base_url + "v1/products"

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        _30_days_ago = (today - timedelta(days=30)).strftime("%Y-%m-%dT%X.000Z")
        tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%dT%X.000Z")

        params = {
            "limit": limit,
            "createdAtMin": from_date if from_date else _30_days_ago,
            "createdAtMax": to_date if to_date else tomorrow,
        }

        if search_term:
            params["search"] = search_term
        if show_errors:
            params["showOnlyUnresolvedErrors"] = True
        data = self._request("GET", url, params=params)
        return data

    def search_batch_deliveries_by_id(
        self, batch_delivery_id, from_date=None, to_date=None, limit=10
    ):
        return self._sonar_search(
            search_term=batch_delivery_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )

    def search_batch_deliveries_by_upc(
        self, upc, from_date=None, to_date=None, limit=10
    ):
        return self._sonar_search(
            search_term=upc, from_date=from_date, to_date=to_date, limit=limit
        )

    def search_batch_deliveries_with_ingestion_failures(
        self, from_date=None, to_date=None, limit=10
    ):
        return self._sonar_search(
            from_date=from_date, to_date=to_date, show_errors=True, limit=limit
        )
