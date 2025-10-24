from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div
from django import forms
from django.urls import reverse

from apps.challenge.challenge_dataset.models import Dataset
from apps.study_management.models import Study
from apps.terminology.models import Code
from apps.user.user_profile.models import Profile


class DataSetCreateForm(forms.ModelForm):
    content = forms.CharField(widget=forms.Textarea(), required=False)
    encrypted = forms.BooleanField(required=False)

    class Meta:
        model = Dataset
        fields = ['name', 'description', 'type']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.helper = FormHelper(self)
        self.fields['content'].label = 'Content. One file identifier string rep per line (system#value).'
        self.helper.layout = Layout(
            'name',
            'type',
            # 'encrypted',
            # 'is_public',
            'description',
            Submit('submit', 'Create')
        )


class GroundTruthForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea())
    legend = forms.ChoiceField()

    # class Meta:
    #     model = GroundTruth
    #     fields = ('content', 'legend', )

    def __init__(self, *args, **kwargs):
        dataset_pk = kwargs.pop('dataset_pk')
        challenge_pk = kwargs.pop('challenge_pk')
        super().__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.form_action = reverse('challenge:challenge_dataset:ground_truth', kwargs=dict(pk=challenge_pk, dataset_pk=dataset_pk))
        self.helper.layout = Layout(
            'content',
            Submit('submit', 'Save', css_class='btn btn-primary')
        )



class QueryForm(forms.Form):
    case_name = forms.CharField(label='Case Name (empty for all cases)', required=False)
    term_autocomplete = forms.CharField(required=False,
                                        label='Terms',
                                        widget=forms.TextInput(attrs={'id': f'term-autocomplete',
                                                                      'placeholder': 'Start typing'}), )
    term_ids = forms.ModelMultipleChoiceField(queryset=Code.objects.all(),
                                              required=False,
                                              widget=forms.MultipleHiddenInput())

    nodes = forms.ModelMultipleChoiceField(queryset=Profile.objects.all(), required=False, widget=forms.CheckboxSelectMultiple())
    # studies = forms.ModelMultipleChoiceField(queryset=Study.objects.all(), required=False, widget=forms.CheckboxSelectMultiple())

    def __init__(self, **kwargs):
        dataset = kwargs.pop('dataset')

        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formQuery'
        qs = Profile.objects.filter(pk__in=list(dataset.challenge.project.get_project_members().values_list('user', flat=True))+[dataset.challenge.project.created_by_id])
        self.fields['nodes'].queryset = qs
        self.fields['nodes'].initial = qs
        # self.fields['studies'].queryset = Study.objects.filter(created_by=)

        self.helper.layout = Layout(
            'case_name',
            'term_autocomplete',
            Div(css_id='div_id_form-terms'),
            'term_ids',
            'nodes',
            Submit('button_preview', 'Preview',
                   **{'hx-post': reverse('challenge:challenge_dataset:project-query', kwargs={'pk': dataset.challenge_id, 'dataset_pk': dataset.pk}),
                      'hx-target': '#queryResults',
                      'hx-include': "input[name='csrfmiddlewaretoken'], #submit-id-button_preview, input[name='term_ids']",
                      'hx-indicator': '.htmx-indicator',
                      'hx-trigger': 'click'}),
            Submit('button_import', 'Import'),
            Div(Div(css_class='progress-bar progress-bar-indeterminate'),
                css_class='progress progress-sm htmx-indicator'),
            Div(css_id='queryResults'),
        )


class ImportDataForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={'accept': '.csv'}))

    def __init__(self, **kwargs):
        dataset = kwargs.pop('dataset', None)
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse('challenge:challenge_dataset:import_csv', kwargs=dict(pk=dataset.challenge_id, dataset_pk=dataset.id_as_str))
        self.helper.layout = Layout(
            'file',
            Submit('submit', 'Submit')
        )


class UpdateDatasetForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ['name', 'type', 'is_public', 'description']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'name',
            'type',
            'is_public',
            'description',
            Submit('submit', 'Save')
        )
