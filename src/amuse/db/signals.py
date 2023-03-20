from django.dispatch import Signal


_model_changed = Signal(providing_args=["instance", "field", "old_value", "new_value"])

model_changed = _model_changed
