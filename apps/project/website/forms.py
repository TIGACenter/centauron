from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, HTML, ButtonHolder
from django import forms

from apps.project.website.models import ProjectWebsite


class ProjectWebsiteForm(forms.ModelForm):

    class Meta:
        model = ProjectWebsite
        fields = ('slogan', 'hero', 'contact_email', 'affiliation')

    def __init__(self, *args, **kwargs):
        super(ProjectWebsiteForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'slogan',
            'hero',
            'contact_email',
            'affiliation',
            ButtonHolder(
                Submit('submit', 'Submit', css_class='btn btn-primary'),
            )
        )
