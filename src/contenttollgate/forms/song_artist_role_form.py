from django import forms
from django.contrib.admin.sites import site
from django.contrib.admin.widgets import ForeignKeyRawIdWidget

from releases.models import SongArtistRole


class SongArtistRoleForm(forms.ModelForm):
    class Meta:
        model = SongArtistRole
        fields = ('artist_sequence', 'artist', 'role', 'song')

        widgets = {
            'artist': ForeignKeyRawIdWidget(
                SongArtistRole._meta.get_field('artist').remote_field,
                site,
                attrs={'class': 'form-control song-artist-role raw-id-field'},
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # # Add bootstrap classes to fields
        text_fields = ('artist_sequence',)
        for field in text_fields:
            self.fields[field].widget.attrs['class'] = 'form-control song-artist-role'

        select_fields = ('role',)
        for field in select_fields:
            self.fields[field].widget.attrs['class'] = 'form-select song-artist-role'

        self.fields['song'].widget = forms.HiddenInput()

        self.fields['artist_sequence'].required = True
