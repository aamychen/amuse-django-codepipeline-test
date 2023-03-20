import logging
from amuse.db.decorators import field_observer
from amuse.mails import send_release_upload_failure
from amuse.services.notifications import (
    CloudMessagingService,
    release_notification_task,
)
from amuse.services import audiorec
from django.conf import settings
from django.dispatch import Signal, receiver
from django.db.models.signals import post_save, m2m_changed
from os.path import splitext
from releases.models import (
    Release,
    ReleaseStoresHistory,
    SongFile,
    SongFileUpload,
    release_completed,
)
from transcoder import Transcoder
from transcoder.signals import (
    transcoder_progress,
    transcoder_complete,
    transcoder_error,
)
from waffle import switch_is_active


logger = logging.getLogger(__name__)


song_file_upload_complete = Signal(providing_args=['instance'])


@field_observer(sender=Release, field='status')
def release_status_changed(sender, instance, old_value, new_value, **kwargs):
    old_status = Release.STATUS_CHOICES[old_value - 1][1]
    new_status = Release.STATUS_CHOICES[new_value - 1][1]
    logger.info(
        "(Signal) Release.%d went from %d to %d (%s -> %s)"
        % (instance.id, old_value, new_value, old_status, new_status)
    )

    if old_value == Release.STATUS_SUBMITTED and new_value == Release.STATUS_PENDING:
        release_notification_task.delay(instance.id)

        if switch_is_active('mail:release:pending'):
            from amuse.tasks import release_went_pending

            release_went_pending.delay(instance.id)

    if (
        old_value == Release.STATUS_APPROVED
        or old_value == Release.STATUS_PENDING
        and new_value == Release.STATUS_DELIVERED
    ):
        release_notification_task.delay(instance.id)

    if old_value == Release.STATUS_SUBMITTED and new_value == Release.STATUS_INCOMPLETE:
        if switch_is_active('mail:release:upload_failure'):
            rel = Release.objects.get(pk=instance.id)
            send_release_upload_failure(rel)


@receiver(song_file_upload_complete)
def song_file_upload_completed(sender, instance, **kwargs):
    release_completed(instance.song.release)


@receiver(post_save, sender=SongFileUpload)
def song_file_upload_post_save(sender, instance, created, **kwargs):
    instance.refresh_from_db()

    if created and instance.link and len(instance.link) > 0:
        from amuse.tasks import download_songfileupload_link

        download_songfileupload_link.delay(instance.id)
        return

    if instance.status is not SongFileUpload.STATUS_COMPLETED:
        return

    if not instance.song:
        return

    if instance.transcode_id is not None:
        return

    input = {'Key': instance.filename}
    outputs = [
        {
            'Key': '{0}.flac'.format(splitext(instance.filename)[0]),
            'PresetId': settings.AWS_FLAC_PRESET_ID,
        },
        {
            'Key': '{0}.mp3'.format(splitext(instance.filename)[0]),
            'PresetId': settings.AWS_MP3128K_PRESET_ID,
        },
    ]

    transcoder = Transcoder(settings.AWS_SONG_FILE_STANDARD_PRIORITY_PIPELINE_ID)
    instance.transcode_id = transcoder.encode(input, outputs)
    instance.save()

    # Trigger audio recognition job
    if switch_is_active("service:audio-recognition:enabled"):
        audiorec.recognize(instance.song.id, instance.filename)


@receiver(transcoder_progress)
def transcoder_progress(sender, message, **kwargs):
    pass


@receiver(transcoder_complete)
def transcoder_complete(sender, message, **kwargs):
    presets = {
        settings.AWS_FLAC_PRESET_ID: SongFile.TYPE_FLAC,
        settings.AWS_MP3128K_PRESET_ID: SongFile.TYPE_MP3,
    }
    song_file_upload = SongFileUpload.objects.get(transcode_id=message['jobId'])
    for output in message['outputs']:
        song_file = SongFile.objects.create(
            type=presets[output['presetId']],
            duration=output['duration'],
            file=output['key'],
            song=song_file_upload.song,
        )
        if song_file.type == SongFile.TYPE_MP3:
            from amuse.tasks import audiblemagic_identify_file

            audiblemagic_identify_file.delay(song_file.id)

        song_file_upload_complete.send(
            sender=song_file_upload, instance=song_file_upload
        )


@receiver(transcoder_error)
def transcoder_error(sender, message, **kwargs):
    pass


@receiver(m2m_changed, sender=Release.stores.through)
def release_stores_changed(sender, action, instance, pk_set, **kwargs):
    pre_actions = ["pre_add", "pre_remove", "pre_clear"]

    if action in pre_actions:
        history = ReleaseStoresHistory.objects.create(release=instance)
        history.stores.set(instance.stores.all())
