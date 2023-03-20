from django import forms

from amuse.models import SupportRelease


class SupportReleaseForm(forms.ModelForm):
    class Meta:
        model = SupportRelease
        fields = ('prepared',)
