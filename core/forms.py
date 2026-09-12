from django import forms

from .models import DirectoryEntry


class DirectoryEntryForm(forms.ModelForm):
    class Meta:
        model = DirectoryEntry
        exclude = ["owner", "slug", "order"]
