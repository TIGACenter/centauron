from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms


class ImportForm(forms.Form):

    file = forms.FileField()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            'file',
            Submit('submit', 'Submit')
        )
