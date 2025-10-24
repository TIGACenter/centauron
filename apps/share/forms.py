from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div
from django import forms
from django.urls import reverse

from apps.core import identifier
from apps.user.user_profile.models import Profile
from django.core.exceptions import ValidationError


class CreateShareForm(forms.Form):
    # TODO only show the nodes here that are added for this user.
    node = forms.ModelChoiceField(queryset=Profile.objects.all())
    project_identifier = forms.CharField(required=False)
    valid_from = forms.DateTimeField()
    valid_until = forms.DateTimeField()
    file_selector = forms.CharField(widget=forms.HiddenInput())
    # percentage of files that should be shared
    percentage = forms.CharField(widget=forms.NumberInput(attrs=dict(min=0, max=100)))

    def __init__(self, **kwargs):
        object = kwargs.pop('object')
        pk = kwargs.pop('pk')

        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formCreateShare'
        self.helper.form_action = reverse('share:create') + f'?object={object}&pk={pk}'
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'node',
            'project_identifier',
            'valid_from',
            'valid_until',
            # Div(id='queryBuilder'),
            'file_selector',
            'percentage'
            # Submit('submit', 'Submit')
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
