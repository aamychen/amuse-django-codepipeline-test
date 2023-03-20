from abc import ABC, abstractmethod
from users.models import User
from rest_framework.request import Request


class AbstractFlow(ABC):
    def __init__(self, skip_artist_creation: bool):
        self.skip_artist_creation = skip_artist_creation

    @abstractmethod
    def pre_registration(self, validated_data: dict) -> None:
        pass

    @abstractmethod
    def post_registration(
        self, request: Request, user: User, validated_data: dict
    ) -> None:
        pass
