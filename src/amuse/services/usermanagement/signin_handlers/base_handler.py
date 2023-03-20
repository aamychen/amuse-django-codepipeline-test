import abc

from rest_framework.request import Request

from users.models import User


class BaseSignInHandler(abc.ABC):
    @abc.abstractmethod
    def authenticate(self, request: Request) -> User:
        pass
