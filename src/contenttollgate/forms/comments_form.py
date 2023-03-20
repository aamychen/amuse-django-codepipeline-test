from django import forms

from releases.models import Comments


class CommentsForm(forms.ModelForm):
    text = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'class': 'form-control comments'})
    )

    class Meta:
        model = Comments
        fields = ('text', 'release')
