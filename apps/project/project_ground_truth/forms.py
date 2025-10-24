import uuid

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django import forms

from apps.core import identifier
from apps.project.project_ground_truth.models import GroundTruthSchema


class GroundTruthSchemaForm(forms.ModelForm):
    class Meta:
        model = GroundTruthSchema
        fields = ['yaml', ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['yaml'].label = 'Schema'

        self.helper = FormHelper(self)
        self.helper.form_id = 'form'
        self.helper.layout = Layout(
            'yaml'
        )

    def save(self, commit=True, **kwargs):
        # on each save create a new object.
        self.instance.pk = uuid.uuid4()
        self.instance.identifier = identifier.create_random('ground-truth-schema')
        self.instance.created_by = kwargs.get('created_by')
        self.instance.project = kwargs.get('project')
        return super().save(commit)
