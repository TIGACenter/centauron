from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, HTML, ButtonHolder, Div
from django import forms

from apps.challenge.website.models import ChallengeWebsite


class ProjectWebsiteForm(forms.ModelForm):
    selected_endpoints = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Select Clinical Endpoints to Display",
        help_text="Choose which clinical endpoints from the ground truth schema to display on the website"
    )

    class Meta:
        model = ChallengeWebsite
        fields = ('slogan', 'hero', 'contact_email', 'affiliation', 'selected_endpoints', 'citation', 'bibtex')

    def __init__(self, *args, **kwargs):
        # Extract challenge from kwargs if provided
        challenge = kwargs.pop('challenge', None)
        super(ProjectWebsiteForm, self).__init__(*args, **kwargs)

        # Get available endpoints from ground truth schema
        available_endpoints = []
        if challenge and challenge.project:
            ground_truth_schema = challenge.project.latest_ground_truth_schema
            if ground_truth_schema:
                # Use the model's get_endpoints method
                endpoints = ground_truth_schema.get_endpoints()
                for endpoint in endpoints:
                    name = endpoint['name']
                    description = endpoint['description']
                    label = f"{name}" + (f" - {description}" if description else "")
                    available_endpoints.append((name, label))

        # Set choices for the endpoint field
        self.fields['selected_endpoints'].choices = available_endpoints

        # Set initial values for selected_endpoints
        if self.instance and self.instance.selected_endpoints:
            self.fields['selected_endpoints'].initial = self.instance.selected_endpoints

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'slogan',
            'hero',
            'contact_email',
            'affiliation',
            Div(
                HTML('<h4 class="mt-4 mb-3">Clinical Endpoints</h4>'),
                'selected_endpoints',
                css_class='endpoint-selection'
            ),
            Div(
                HTML('<h4 class="mt-4 mb-3">Citation Information</h4>'),
                'citation',
                'bibtex',
                css_class='citation-section'
            ),
            ButtonHolder(
                Submit('submit', 'Submit', css_class='btn btn-primary'),
            )
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Ensure selected_endpoints is stored as a list
        if isinstance(self.cleaned_data.get('selected_endpoints'), list):
            instance.selected_endpoints = self.cleaned_data['selected_endpoints']
        if commit:
            instance.save()
        return instance

