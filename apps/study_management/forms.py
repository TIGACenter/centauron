from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms
from django.urls import reverse

from apps.core import identifier
from apps.study_management.models import Study


class StudyForm(forms.ModelForm):
    class Meta:
        model = Study
        fields = ('name',)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            Submit('submit', 'Create')
        )

    def save(self, commit: bool = True, **kwargs):
        self.instance.identifier = identifier.create_random('study')
        self.instance.created_by = kwargs.get('created_by')
        return super().save(commit)


class UpdateForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={'accept': '.csv'}))

    def __init__(self, **kwargs):
        study = kwargs.pop('study', None)
        arm_pk = kwargs.pop('arm', None)
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse('study_management:arm-update', kwargs=dict(pk=study.id_as_str, arm_pk=arm_pk))
        self.helper.layout = Layout(
            'file',
            Submit('submit', 'Submit')
        )
