from django import forms

from releases.models import CoverArt


class CustomClearableFileInput(forms.ClearableFileInput):
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['is_initial'] = False
        return context


class CoverArtForm(forms.ModelForm):
    file = forms.ImageField(
        label='Replace CoverArt file',
        required=False,
        widget=CustomClearableFileInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = CoverArt
        fields = ('file',)
