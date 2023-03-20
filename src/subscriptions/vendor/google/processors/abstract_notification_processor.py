from abc import ABC, abstractmethod


class AbstractNotificationProcessor(ABC):
    def __init__(self, data):
        self.data = data

    @abstractmethod
    def process(self, event_id):
        pass
