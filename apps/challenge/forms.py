from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms

from apps.challenge.challenge_dataset.models import EvaluationCode
from apps.challenge.models import Challenge
from apps.core import identifier
from apps.project.models import Project


class CreatePipelineForm(forms.Form):
    yml = forms.CharField(widget=forms.Textarea(attrs=dict(rows=10)))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields['yml'].label = 'Paste your pipeline yml here:'
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'yml',
            Submit('submit', 'Submit')
        )


class CreateChallengeForm(forms.ModelForm):
    class Meta:
        model = Challenge
        fields = ('name', 'description', 'open_from', 'open_until', 'project')

    def __init__(self, **kwargs):
        user = kwargs.pop('user')
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.fields['project'].queryset = Project.objects.for_user_owner(user)
        self.helper.layout = Layout(
            'name',
            'description',
            'open_from',
            'open_until',
            'project',
            Submit('submit', 'Submit')
        )

    def save(self, commit=True, **kwargs):
        self.instance.created_by = kwargs.get('created_by')
        self.instance.origin = kwargs.get('created_by')
        self.instance.identifier = identifier.create_random('challenge')
        return super().save(commit)


class EvaluationCodeForm(forms.ModelForm):
    class Meta:
        model = EvaluationCode
        fields = ('name', 'schema', 'pyscript')

    def __init__(self, **kwargs):
        project = kwargs.pop('project')
        super().__init__(**kwargs)
        self.fields['schema'].label_from_instance = self.schema_label
        self.fields['schema'].queryset = project.ground_truth_schemas.order_by('-date_created')

        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'schema',
            'pyscript',
            Submit('save', 'Save')
        )

    def schema_label(self, obj):
        d = obj.date_created.isoformat()
        if len(obj.name.strip()) == 0:
            return f'{obj.identifier} ({d})'
        return f'{obj.name} ({d})'

class UpdateChallengeForm(forms.ModelForm):
    class Meta:
        model = Challenge
        fields = ['name', 'description', 'open_from', 'open_until']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'description',
            'open_from',
            'open_until',
            Submit('submit', 'Save')
        )
