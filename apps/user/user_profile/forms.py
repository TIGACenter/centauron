from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms

from apps.user.user_profile.models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['human_readable', 'orcid', 'pubmed', 'google_scholar', 'organization']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            'human_readable',
            'organization',
            'orcid',
            'pubmed',
            'google_scholar',
            Submit('submit', 'Save'),
            Submit('save_and_publish', 'Save and publish'),
        )
