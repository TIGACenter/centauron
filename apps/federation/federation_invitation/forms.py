from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms

from apps.federation.federation_invitation.models import FederationInvitation
from apps.user.user_profile.models import Profile


class CreateInvitationForm(forms.ModelForm):
    project = forms.CharField(show_hidden_initial=True)
    from_user = forms.ModelChoiceField(show_hidden_initial=True, queryset=Profile.objects.all())

    class Meta:
        model = FederationInvitation
        fields = ('from_user',)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields['from_user'].widget = self.fields['from_user'].hidden_widget()
        self.fields['project'].widget = self.fields['project'].hidden_widget()

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            'from_user',
            'project',
            Submit('connect', 'Connect')
        )
