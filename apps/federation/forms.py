from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms
from django.urls import reverse

from apps.user.user_profile.models import Profile


class ImportInboxMessage(forms.Form):
    code = forms.CharField(widget=forms.Textarea())
    sender = forms.ModelChoiceField(queryset=Profile.objects.all())
    recipient = forms.ModelChoiceField(queryset=Profile.objects.all())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.fields['code']


class ImportCodeForm(forms.Form):
    code = forms.CharField(widget=forms.Textarea())
    user = forms.ModelChoiceField(queryset=Profile.objects.all())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.fields['code']


class AddNodeForm(forms.Form):
    code = forms.CharField(widget=forms.Textarea(attrs={'placeholder': 'Paste code here'}))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.form_action = reverse('federation:add-node')
        self.helper.layout = Layout(
            'code',
            Submit('submit', 'Add node')
        )
