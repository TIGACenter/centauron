from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div
from django import forms
from django.urls import reverse

from apps.study_management.models import Study
from apps.terminology.models import Code


class ImportDataForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={'accept': '.csv'}))

    def __init__(self, **kwargs):
        project = kwargs.pop('project', None)
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse('project:import_data:csv', kwargs=dict(pk=project.id_as_str))
        self.helper.layout = Layout(
            'file',
            Submit('submit', 'Submit')
        )

class ImportFromNodeForm(forms.Form):
    code = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}))

    def __init__(self, **kwargs):
        project = kwargs.pop('project', None)
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse('project:import_data:node', kwargs=dict(pk=project.id_as_str))
        self.helper.layout = Layout(
            'code',
            Submit('submit', 'Submit')
        )



class AddDataToProjectForm(forms.Form):
    study = forms.ModelChoiceField(queryset=Study.objects.all(), label='Cohort', required=False,
                                   empty_label='All cohorts')
    term_autocomplete = forms.CharField(required=False,
                                        label='Terms',
                                        widget=forms.TextInput(attrs={'id': f'term-autocomplete',
                                                                      'placeholder': 'Start typing'}), )
    term_ids = forms.ModelMultipleChoiceField(queryset=Code.objects.all(),
                                              required=False,
                                              widget=forms.MultipleHiddenInput())

    def __init__(self, **kwargs):
        user = kwargs.pop('user')
        project = kwargs.pop('project')
        super().__init__(**kwargs)

        self.fields['study'].queryset = Study.objects.for_user(user)

        self.helper = FormHelper()
        self.helper.form_id = 'formQuery'
        self.helper.layout = Layout(
            'study',
            'term_autocomplete',
            Div(css_id='div_id_form-terms'),
            'term_ids',
            Submit('button_preview', 'Preview', **{'hx-post': reverse('project:import_data:add-data', kwargs={'pk': project.pk}),
                                                   'hx-target': '#queryResults',
                                                   'hx-include': "input[name='csrfmiddlewaretoken'], #submit-id-button_preview, input[name='term_ids']",
                                                   'hx-indicator': '.htmx-indicator',
                                                   'hx-trigger': 'click'}),
            Submit('button_import', 'Import'),
            Div(Div(css_class='progress-bar progress-bar-indeterminate'),
                css_class='progress progress-sm htmx-indicator'),
            Div(css_id='queryResults')
        )


class ImportAnnotationFromExactForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={'accept': '.json, .txt'}))

    def __init__(self, **kwargs):
        user = kwargs.pop('user')
        project = kwargs.pop('project', None)
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse('project:import_data:exact', kwargs=dict(pk=project.id_as_str))
        self.helper.layout = Layout(
            'file',
            Submit('submit', 'Submit')
        )

