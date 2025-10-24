from django import forms


class DialogAddForm(forms.Form):
    code_id = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
