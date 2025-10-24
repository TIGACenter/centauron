from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django import forms

from apps.node.models import Node
from apps.permission.models import Permission


class CreateForm(forms.Form):
    node = forms.ModelChoiceField(queryset=Node.objects.all())
    valid_from = forms.DateTimeField()
    valid_until = forms.DateTimeField()
    permissions = forms.MultipleChoiceField(choices=Permission.Action)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'node'
        )
