import functools
from django.db.models.signals import post_save, post_init, post_delete
from simple_history.models import HistoricalRecords
from .signals import model_changed


def _observable_fields(exclude=()):
    def _store_loaded_fields(obj):
        obj._loaded_values = dict(
            [
                (f.name, getattr(obj, f.name, None))
                for f in obj._meta.local_fields
                if f.name not in exclude
            ]
        )

    def _raise_changed_events(obj):
        updated = obj.get_updated_fields()

        for field, diff in updated.items():
            old, new = diff['was'], diff['new']
            model_changed.send(
                sender=obj.__class__,
                instance=obj,
                field=field,
                old_value=old,
                new_value=new,
            )

    def decoration(cls):
        def _get_updated_fields(self):
            new = dict(
                [(f.name, getattr(self, f.name, None)) for f in self._meta.local_fields]
            )
            diff = dict(
                [
                    (field, dict(was=old_val, new=new[field]))
                    for field, old_val in self._loaded_values.items()
                    if old_val != new[field]
                ]
            )
            return diff

        cls.get_updated_fields = _get_updated_fields

        def _post_init(sender, instance, **kwargs):
            _store_loaded_fields(instance)

        def _post_save(sender, instance, **kwargs):
            _raise_changed_events(instance)

        post_init.connect(_post_init, sender=cls, weak=False)
        post_save.connect(_post_save, sender=cls, weak=False)

        return cls

    return decoration


def _field_observer(sender, field):
    _field = field

    def _decorate(callback):
        @functools.wraps(callback)
        def _decorated_callback(
            sender, instance, field, old_value, new_value, **kwargs
        ):
            if _field == field:
                callback(sender, instance, old_value, new_value, **kwargs)

        model_changed.connect(_decorated_callback, sender=sender)
        return _decorated_callback

    return _decorate


def with_history(cls):
    """
    Applies Django Simple History fields to a model.

    Tracks Create, Update, and Deletes for an object and
    exposes `.history` property where the object history is accessible.

    http://django-simple-history.readthedocs.io/en/latest/usage.html#models

    This code is roughly identical to simple_history.register() except for
    it understanding that models that have super models may already have history
    applied. In that case no tables for history should be created, which happens in
    HistoricalRecords.finalize(). Only hook up signals.

    https://amuseio.atlassian.net/browse/PR-1113
    """
    # Find out if this is a proxy model inheriting from another model with
    # history. If so, use the same table and module name.
    table_name = None
    app = None
    if cls._meta.proxy and hasattr(cls, 'history'):
        table_name = cls.history.model._meta.db_table
        app = cls.history.model._meta.app_label

    records = HistoricalRecords(table_name=table_name)
    records.manager_name = 'history'
    records.module = app and ("%s.models" % app) or cls.__module__
    records.cls = cls
    records.add_extra_methods(cls)

    if table_name:
        # Hook up signals only as in HistoricalRecords.finalize().
        post_save.connect(records.post_save, sender=cls, weak=False)
        post_delete.connect(records.post_delete, sender=cls, weak=False)
    else:
        # Create history model, hook up signals etc
        records.finalize(cls)

    return cls


observable_fields = _observable_fields
field_observer = _field_observer
