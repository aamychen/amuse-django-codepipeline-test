from django import forms
from django.contrib.admin.sites import site
from django.contrib.admin.widgets import ForeignKeyRawIdWidget

from releases.models import ReleaseArtistRole, SongArtistRole


class ReleaseArtistRoleForm(forms.ModelForm):
    class Meta:
        model = ReleaseArtistRole
        fields = ('artist_sequence', 'artist', 'role', 'main_primary_artist', 'release')

        widgets = {
            'artist': ForeignKeyRawIdWidget(
                ReleaseArtistRole._meta.get_field('artist').remote_field,
                site,
                attrs={'class': 'form-control release-artist-role raw-id-field'},
            )
        }

    def __init__(self, *args, **kwargs):
        self.song_artist_roles_formsets = kwargs.pop('song_artist_roles_formsets')

        super().__init__(*args, **kwargs)

        # # Add bootstrap classes to fields
        text_fields = ('artist_sequence',)
        for field in text_fields:
            self.fields[field].widget.attrs['class'] = 'form-control'

        select_fields = ('role', 'main_primary_artist')
        for field in select_fields:
            self.fields[field].widget.attrs['class'] = 'form-select'

        if self.instance.artist_sequence == 1:
            self.fields['artist_sequence'].widget.attrs['readonly'] = True
            self.fields['artist'].disabled = True
            self.fields['role'].disabled = True
            self.fields['main_primary_artist'].disabled = True

        self.fields['release'].widget = forms.HiddenInput()

    def clean(self):
        super().clean()

        primary_artist_ids_on_song_level = self.get_primary_artist_ids_on_song_level()

        if (
            self.cleaned_data['main_primary_artist']
            and self.cleaned_data['artist'].id not in primary_artist_ids_on_song_level
        ):
            self.add_error(
                'artist', 'Main artist must be a primary artist on at-least one song'
            )

    def get_primary_artist_ids_on_song_level(self):
        artist_ids = []
        for song_artist_role_formset in self.song_artist_roles_formsets.values():
            for song_artist_role in song_artist_role_formset:
                role = song_artist_role.cleaned_data.get('role', None)
                artist = song_artist_role.cleaned_data.get('artist', None)

                if role and artist and role == SongArtistRole.ROLE_PRIMARY_ARTIST:
                    artist_ids.append(artist.id)

        return artist_ids
