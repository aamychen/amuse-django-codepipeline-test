from django import forms
from django.core.exceptions import ValidationError
from django.contrib.admin.sites import site
from django.contrib.admin.widgets import ForeignKeyRawIdWidget

from countries.models import Country
from releases.models import Store, Release, MetadataLanguage
from releases.utils import RELEASE_ALLOWED_FLAGS


class ReleaseForm(forms.ModelForm):
    stores = forms.ModelMultipleChoiceField(
        queryset=Store.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'custom-select release'}),
    )

    excluded_countries = forms.ModelMultipleChoiceField(
        queryset=Country.objects.all().order_by('name'),
        required=False,
        widget=forms.SelectMultiple(
            attrs={'class': 'custom-select release', 'size': '7'}
        ),
    )

    class Meta:
        model = Release
        fields = (
            'name',
            'label',
            'release_version',
            'type',
            'release_date',
            'original_release_date',
            'genre',
            'upc',
            'meta_language',
            'status',
            'error_flags',
            'stores',
            'excluded_countries',
        )
        raw_id_fields = ('upc',)
        widgets = {
            'release_date': forms.DateInput(
                attrs={
                    'class': 'form-control release',
                    'placeholder': 'YYYY/MM/DD',
                    'type': 'date',
                }
            ),
            'original_release_date': forms.DateInput(
                attrs={
                    'class': 'form-control release',
                    'placeholder': 'YYYY/MM/DD',
                    'type': 'date',
                }
            ),
            'upc': ForeignKeyRawIdWidget(
                Release._meta.get_field("upc").remote_field,
                site,
                attrs={'class': 'form-control release raw-id-field'},
            ),
        }

    def __init__(self, *args, **kwargs):
        stores_queryset = kwargs.pop('stores_queryset')
        super().__init__(*args, **kwargs)
        self.fields['stores'].queryset = stores_queryset

        self.fields['stores'].widget.attrs['size'] = stores_queryset.count()

        # Filter out instrumental as it's not a valid metadata language
        instrumental_language = MetadataLanguage.objects.filter(fuga_code='zxx').first()
        if instrumental_language:
            choices = self.fields['meta_language'].choices
            self.fields['meta_language'].choices = [
                (k, v) for k, v in choices if k != instrumental_language.id
            ]

        # # Add bootstrap classes to fields
        text_fields = ('name', 'label', 'release_version')
        for field in text_fields:
            self.fields[field].widget.attrs['class'] = 'form-control release'

        select_fields = ('type', 'status', 'genre', 'meta_language')
        for field in select_fields:
            self.fields[field].widget.attrs['class'] = 'form-select release'

    def clean(self):
        super().clean()

        if (
            not self.is_valid()
            or self.cleaned_data["status"] != Release.STATUS_APPROVED
        ):
            return

        if self.cleaned_data["error_flags"] not in RELEASE_ALLOWED_FLAGS:
            raise ValidationError("Error flags not allowed for status Approved")

        if self.cleaned_data["stores"].count() == 0:
            raise ValidationError("No stores not allowed for status Approved")
