from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout
from django import forms
from django.contrib.auth import get_user_model
from keycloak import KeycloakAuthenticationError

from apps.user.user_profile.models import Profile
from apps.utils import get_keycloak_admin

User = get_user_model()


class SubmissionCreateForm(forms.Form):
    name = forms.CharField(required=False)
    # image = forms.CharField(required=True)
    # script = forms.CharField(required=True)
    # credentials = forms.CharField(required=True)
    local = forms.BooleanField(widget=forms.HiddenInput, required=False)

    def __init__(self, **kwargs):
        fields = kwargs.pop('fields', [])
        self.template_identifier = kwargs.pop('template_identifier', None)
        super().__init__(**kwargs)
        # self.fields['']

        for f in fields:
            self.fields[f] = forms.CharField(required='credentials' not in f)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            *[f for f in fields],
            'local',
            # 'docker_image',
            # 'entry_point',
            Submit('submit', 'Submit')
        )


# class UserRegistrationForm(forms.ModelForm):
#     password = forms.CharField(widget=forms.PasswordInput)
#     confirm_password = forms.CharField(widget=forms.PasswordInput)
#
#     class Meta:
#         model = User
#         fields = ['username', 'email', 'password']
#
#     def clean(self):
#         cleaned_data = super().clean()
#         password = cleaned_data.get("password")
#         confirm_password = cleaned_data.get("confirm_password")
#
#         if password and confirm_password and password != confirm_password:
#             self.add_error("confirm_password", "Passwords do not match.")
#
#         return cleaned_data

class ProfileForm(forms.ModelForm):

    email = forms.EmailField(required=True)

    class Meta:
        model = Profile
        fields = ['email', 'human_readable', 'organization', 'orcid', 'pubmed', 'google_scholar']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['human_readable'].label = 'Your name'
        self.fields['email'].label = 'Your email address'
        self.fields['organization'].label = 'Research Institute / Organization'
        self.fields['orcid'].label = 'Link to your ORCID profile'
        self.fields['pubmed'].label = 'Link to your PubMED profile'
        self.fields['google_scholar'].label = 'Link to your Google Scholar profile'

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'email',
            'human_readable',
            'organization',
            'orcid',
            'pubmed',
            'google_scholar',
            Submit('submit', 'Register')
        )

    def clean(self):
        cleaned_data = super().clean()

        try:
            keycloak_admin = get_keycloak_admin()
        except KeycloakAuthenticationError as e:
            raise e

        query_username = keycloak_admin.get_users(query={
            'email': self.cleaned_data['email'],
            'exact': True})

        if len(query_username) > 0:
            self.add_error("email", "Email already taken.")

        return cleaned_data
