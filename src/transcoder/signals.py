from django.dispatch import Signal

transcoder_progress = Signal(providing_args=['message'])
transcoder_complete = Signal(providing_args=['message'])
transcoder_error = Signal(providing_args=['message'])
