from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from amuse.utils import CLIENT_OPTIONS
from countries.models import Country


class EventQuerySet(models.QuerySet):
    def content_object(self, obj):
        return self.filter(
            content_type__pk=ContentType.objects.get_for_model(obj).pk, object_id=obj.pk
        )

    def type(self, type):
        return self.filter(type=type)


class Event(models.Model):
    TYPE_CREATE = 1
    TYPE_UPDATE = 2
    TYPE_LOGIN = 3

    TYPE_OPTIONS = {TYPE_CREATE: 'create', TYPE_UPDATE: 'update', TYPE_LOGIN: 'login'}

    type = models.PositiveIntegerField(
        choices=[(k, v) for k, v in TYPE_OPTIONS.items()]
    )

    client = models.PositiveIntegerField(
        choices=[(k, v) for k, v in CLIENT_OPTIONS.items()]
    )
    version = models.CharField(max_length=32)

    ip = models.GenericIPAddressField(db_index=True)
    country = models.ForeignKey(Country, null=True, on_delete=models.PROTECT)

    date_created = models.DateTimeField(auto_now_add=True)

    object_id = models.PositiveIntegerField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object = GenericForeignKey()

    objects = EventQuerySet.as_manager()

    def __repr__(self):
        return '<#{} type={} client={} version={} ip={} country={} date_created={} object_id={} content_type={} object={}'.format(
            self.id,
            self.type,
            self.client,
            self.version,
            self.ip,
            self.country,
            self.date_created,
            self.object_id,
            self.content_type,
            self.object,
        )
