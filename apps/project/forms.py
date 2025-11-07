from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div
from django import forms
from django.urls import reverse

from apps.core import identifier
from apps.node.models import Node
from apps.project.models import Project
from apps.terminology.models import Code


class SendDataToAnnotatorForm(forms.Form):
    dataset_id = forms.CharField()
    project_id = forms.CharField()
    query = forms.CharField(widget=forms.Textarea())
    codes = forms.ModelMultipleChoiceField(widget=forms.CheckboxSelectMultiple(), queryset=Code.objects.all(),
                                           label='Labels', required=False)

    def __init__(self, **kwargs):
        project = kwargs.pop('project')
        super().__init__(**kwargs)
        self.fields['codes'].queryset = project.codeset.codes.all()
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'dataset_id',
            'project_id',
            'query',
            'codes',
            Submit('submit', 'Submit')
        )


class AddCollaboratorForm(forms.Form):
    node = forms.ModelChoiceField(
        queryset=Node.objects.all())  # FIXME all_but_me() # TODO do not show the nodes that are already in project

    def __init__(self, **kwargs):
        project_id = None
        if 'project_id' in kwargs:
            project_id = kwargs.pop('project_id')
        qs = None
        if 'queryset' in kwargs:
            qs = kwargs.pop('queryset')
        super().__init__(**kwargs)
        if qs is not None:
            self.fields['node'].queryset = qs
        self.helper = FormHelper()
        if project_id is not None:
            self.helper.form_action = reverse('project:collaborator-add', kwargs=dict(pk=project_id))
        self.helper.layout = Layout(
            'node',
            Submit('submit', 'Add')
        )


class DownloadDataForm(forms.Form):
    query = forms.CharField(widget=forms.Textarea())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'query',
            Div(
                Submit('query', 'Query'),
                Submit('download', 'Download'),
            )
        )


class CreateProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'intended_use', 'population', 'biomarkers_autocomplete',
                  'biomarkers_ids',
                  'tissue_autocomplete',
                  'tissue_ids',
                  'disease_autocomplete',
                  'disease_ids', ]

        help_texts = {
            "description": '<a href="https://www.markdownguide.org/basic-syntax/" target="_blank">Markdown</a> allowed',
            "intended_use": '<a href="https://www.markdownguide.org/basic-syntax/" target="_blank">Markdown</a> allowed',
            "population": '<a href="https://www.markdownguide.org/basic-syntax/" target="_blank">Markdown</a> allowed',
        }

    biomarkers_autocomplete = forms.CharField(required=False,
                                              label='Biomarkers',
                                              widget=forms.TextInput(attrs={'id': f'term-autocomplete-biomarkers',
                                                                            'placeholder': 'Start typing'}), )
    biomarkers_ids = forms.ModelMultipleChoiceField(queryset=Code.objects.all(),
                                                    required=False,
                                                    widget=forms.MultipleHiddenInput())

    tissue_autocomplete = forms.CharField(required=False,
                                          label='Tissues',
                                          widget=forms.TextInput(attrs={'id': f'term-autocomplete-tissue',
                                                                        'placeholder': 'Start typing'}), )
    tissue_ids = forms.ModelMultipleChoiceField(queryset=Code.objects.all(),
                                                required=False,
                                                widget=forms.MultipleHiddenInput())

    disease_autocomplete = forms.CharField(required=False,
                                           label='Diseases',
                                           widget=forms.TextInput(attrs={'id': f'term-autocomplete-disease',
                                                                         'placeholder': 'Start typing'}), )
    disease_ids = forms.ModelMultipleChoiceField(queryset=Code.objects.all(),
                                                 required=False,
                                                 widget=forms.MultipleHiddenInput())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.helper = FormHelper()
        self.helper.form_id = 'formQuery'
        self.helper.layout = Layout(
            'name',
            'description',
            'intended_use',
            'population',
            'biomarkers_autocomplete',
            'biomarkers_ids',
            Div(css_id='div_id_form-biomarkers_ids'),
            'tissue_autocomplete',
            'tissue_ids',
            Div(css_id='div_id_form-tissue_ids'),
            'disease_autocomplete',
            'disease_ids',
            Div(css_id='div_id_form-disease_ids'),

            Submit('submit', 'Submit')
        )

    def save(self, commit: bool = True, **kwargs):
        self.instance.created_by = kwargs.get('created_by')
        self.instance.origin = kwargs.get('created_by')
        self.instance.identifier = identifier.create_random('project')
        return super().save(commit)
