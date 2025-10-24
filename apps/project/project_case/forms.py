from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django import forms
from django.core.exceptions import ValidationError
from django.forms import modelformset_factory, BaseModelFormSet, SelectMultiple, Widget

from apps.core import identifier
from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.terminology.models import Code
from apps.utils import get_node_origin


class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ('name',)

    def __init__(self, **kwargs):
        # self.study_arm = kwargs.get('study_arm', None)
        super().__init__(**kwargs)

        self.helper = FormHelper()
        self.helper.form_id = 'create-case'
        self.layout = Layout(
            'name',
        )

    # def save(self, commit: bool = True):
    #     case = super().save(commit)
    #     # StudyArm.
    #     # add the file


class FileForm(forms.ModelForm):
    # terms = forms.CharField()
    # terms = forms.CharField(widget=forms.HiddenInput())

    class Meta:
        model = File
        fields = ('name',)

    def __init__(self, **kwargs):
        self.study_arm = kwargs.pop('study_arm')
        self.created_by = kwargs.pop('created_by')
        self.case = kwargs.pop('case')
        super().__init__(**kwargs)
        self.fields['name'].required = False
        self.file = kwargs.get('instance', None)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) == 0:
            raise ValidationError('Name cannot be empty')
        return name

    def save(self, commit: bool = True):
        file = super().save(commit=False)
        # add file to this study arm
        file.created_by = self.created_by
        file.identifier = identifier.create_random('file')
        file.origin = self.created_by
        # super().get_context()
        file.case = self.case
        file.save()
        self.study_arm.files.add(file)


class CodeSelectMultipleInput(SelectMultiple):
    template_name = "forms/select_tags.html"


# class CodeField(forms.ModelMultipleChoiceField):
#     widget = SelectMultiple
#     def __init__(self, queryset: None, **kwargs):
#         super().__init__(queryset, **kwargs)

class TagInput(Widget):
    template_name = "forms/select_tags.html"

    def __init__(self, queryset, file, index, **kwargs):
        super().__init__(**kwargs)
        self.queryset = queryset
        self.file = file
        self.index = index

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx['widget']['queryset'] = self.queryset
        ctx['widget']['index'] = self.index
        ctx['widget']['file'] = self.file
        return ctx


class TagField(forms.Field):
    widget = TagInput


class AddFileFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = 'post'
        self.form_id = 'formFiles'
        self.layout = Layout(
            'name',
            'terms',
            'autocomplete',
            'term_ids'
            # 'terms'
            # HTML('<input id="autoComplete" class="form-control">')
        )
        self.render_required_fields = True
        self.template = 'crispy_bootstrap5/table_inline_formset.html'


class BaseAddFileFormSet(BaseModelFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields['terms'] = TagField(disabled=True, required=False,
                                        widget=TagInput(queryset=form.instance.codes.all(), file=form.instance,
                                                        index=index))
        form.fields['term_ids'] = forms.ModelMultipleChoiceField(initial=form.instance.codes.all(),
                                                                 queryset=Code.objects.all(),
                                                                 required=False,
                                                                 widget=forms.MultipleHiddenInput())
        form.fields['autocomplete'] = forms.CharField(required=False,
                                                      label='Add term',
                                                      widget=forms.TextInput(attrs={'id': f'autocomplete-{index}',
                                                                                    'placeholder': 'Start typing'}), )


AddFileFormSet = modelformset_factory(model=File, extra=1, form=FileForm, formset=BaseAddFileFormSet, can_delete=True)
