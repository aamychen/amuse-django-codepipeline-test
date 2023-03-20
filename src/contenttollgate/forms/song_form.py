from django import forms
from django.core.exceptions import ValidationError
from django.contrib.admin.widgets import ForeignKeyRawIdWidget
from django.contrib.admin.sites import site

from releases.models import MetadataLanguage, Release, Song
from releases.utils import SONG_ALLOWED_FLAGS


class SongForm(forms.ModelForm):
    class Meta:
        model = Song
        fields = (
            'name',
            'sequence',
            'recording_year',
            'version',
            'isrc',
            'genre',
            'meta_language',
            'meta_audio_locale',
            'explicit',
            'origin',
            'preview_start_time',
            'youtube_content_id',
            'error_flags',
        )
        raw_id_fields = ('isrc',)
        widgets = {
            'isrc': ForeignKeyRawIdWidget(
                Song._meta.get_field("isrc").remote_field,
                site,
                attrs={'class': 'form-control song raw-id-field'},
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter out instrumental as it's not a valid metadata language
        instrumental_language = MetadataLanguage.objects.filter(fuga_code='zxx').first()
        if instrumental_language:
            choices = self.fields['meta_language'].choices
            self.fields['meta_language'].choices = [
                (k, v) for k, v in choices if k != instrumental_language.id
            ]

        # # Add bootstrap classes to fields
        text_fields = (
            'name',
            'sequence',
            'recording_year',
            'version',
            'preview_start_time',
        )
        for field in text_fields:
            self.fields[field].widget.attrs['class'] = 'form-control song'

        select_fields = (
            'genre',
            'meta_language',
            'meta_audio_locale',
            'origin',
            'explicit',
            'youtube_content_id',
        )
        for field in select_fields:
            self.fields[field].widget.attrs['class'] = 'form-select song'

        self.fields['error_flags'].widget.attrs['class'] = 'form-check-input'

    def clean(self):
        super().clean()

        if not self.is_valid() or self.data.get("release-status") != str(
            Release.STATUS_APPROVED
        ):
            return

        if self.cleaned_data["error_flags"] not in SONG_ALLOWED_FLAGS:
            raise ValidationError("Error flags not allowed for status Approved")
