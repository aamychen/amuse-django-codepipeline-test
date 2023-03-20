from rest_framework.request import Request

from amuse.api.base.validators import validate_artist_name
from users.models import User
from .abstract_flow import AbstractFlow
from .common import Common


class RegularFlow(AbstractFlow):
    def __init__(self):
        super(RegularFlow, self).__init__(False)

    def pre_registration(self, validated_data: dict) -> None:
        validate_artist_name(validated_data)

    def post_registration(
        self, request: Request, user: User, validated_data: dict
    ) -> None:
        Common.send_signup_completed_event(request, user, 'regular')
