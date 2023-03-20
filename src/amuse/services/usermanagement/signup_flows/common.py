from rest_framework.request import Request

from amuse.platform import PlatformHelper
from amuse.tasks import send_segment_signup_completed_event
from countries.models import Country


class Common:
    @classmethod
    def send_signup_completed_event(cls, request: Request, user, signup_path):
        platform_name = PlatformHelper.from_request(request).name.lower()
        detected_country_name = cls._get_country_name(request)
        send_segment_signup_completed_event.delay(
            user, platform_name, detected_country_name, signup_path
        )

    @classmethod
    def _get_country_name(cls, request: Request):
        detected_country_name = None
        detected_country_code = request.META.get('HTTP_CF_IPCOUNTRY')
        detected_country = Country.objects.filter(code=detected_country_code).first()
        if detected_country is not None:
            detected_country_name = detected_country.name
        return detected_country_name
