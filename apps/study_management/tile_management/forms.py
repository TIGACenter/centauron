from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms
from django.core.exceptions import ValidationError

from apps.core import identifier
from apps.user.user_profile.models import Profile


class ImportCSVForm(forms.Form):
    file = forms.FileField()
    name = forms.CharField()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'file',
            Submit('submit', 'Submit')
        )

class UpdateForm(forms.Form):
    file = forms.FileField()
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'file',
            Submit('submit', 'Submit')
        )

class ShareTileSetForm(forms.Form):
    node = forms.ModelChoiceField(queryset=Profile.objects.all())
    project_identifier = forms.CharField(required=False)
    valid_from = forms.DateTimeField()
    valid_until = forms.DateTimeField()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'node',
            'project_identifier',
            'valid_from',
            'valid_until',
            Submit('submit', 'Submit')
        )

    def clean_project_identifier(self):
        data = self.cleaned_data['project_identifier'].strip()
        if len(data) > 0:
            id = identifier.from_string(data)
            if id is None:
                raise ValidationError('No valid identifier.')
        return data

    def clean_valid_until(self):
        valid_from = self.cleaned_data['valid_from']
        valid_until = self.cleaned_data['valid_until']

        if valid_until < valid_from:
            raise ValidationError('valid until must be after valid from.')

        return valid_until
