# -*- coding: utf-8 -*-


class Payload:
    def __init__(self, to=None, notification=None, data=None):
        self.to = to
        self.notification = notification
        self.data = data


class Notification:
    def __init__(self, title=None, body=None):
        self.title = title
        self.body = body
