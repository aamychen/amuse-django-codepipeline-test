# -*- coding: utf-8 -*-
import json

from django.db import models
from django.db.models import JSONField


class JSONTransformator(JSONField):
    def from_db_value(self, value, *args, **kwargs):
        if isinstance(value, str):
            return json.loads(value)
        return value


class BaseDataStore(models.Model):
    data = JSONTransformator()

    class Meta:
        abstract = True

    def __str__(self):
        try:
            return self.data['key']
        except KeyError:
            return ''


class NotificationTemplate(BaseDataStore):
    name = models.CharField(max_length=240)

    class Meta:
        db_table = 'notification_template'

    @property
    def key(self):
        try:
            return self.data['key']
        except KeyError:
            pass
