from abc import ABC, abstractmethod

from releases.models import Release, Store


class DeliveryCheck(ABC):
    failure_message: str = None

    def __init__(self, release: Release, store: Store, operation: str):
        self.release = release
        self.store = store
        self.operation = operation

    @abstractmethod
    def passing(self) -> bool:
        raise NotImplementedError()
