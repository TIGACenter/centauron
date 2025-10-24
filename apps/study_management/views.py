import csv
import datetime
import itertools
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.files.uploadedfile import UploadedFile
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import TemplateView, CreateView, FormView

from apps.core import identifier
from apps.core.views import BaseTableActionView
from apps.project.project_case.forms import CaseForm, AddFileFormSet, AddFileFormSetHelper
from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.storage.storage_importer.models import ImportFolder
from apps.study_management.forms import StudyForm, UpdateForm
from apps.study_management.import_data.tasks import run_metadata_updater
from apps.study_management.models import Study, StudyArm
from apps.study_management.tasks import export_arm_files_to_csv, export_imported_files_to_csv, \
    export_arm_files_column_values, EXPORT_ARM_FILES_COLUMNS


class StudyListView(LoginRequiredMixin, TemplateView):
    template_name = 'study_management/list.html'


class StudyDetailMixin:

    def get_study_pk(self):
        return self.kwargs.get('pk', None)

    def get_study(self):
        return get_object_or_404(Study, pk=self.get_study_pk())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['study'] = self.get_study()
        return ctx


class StudyArmDetailMixin:

    def get_study_arm_pk(self):
        return self.kwargs.get('arm_pk', None)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['arm'] = get_object_or_404(StudyArm, pk=self.get_study_arm_pk(), study_id=self.kwargs.get('pk'),
                                       study__created_by=self.request.user.profile)
        return ctx


class StudyDetailView(LoginRequiredMixin, StudyDetailMixin, TemplateView):
    template_name = 'study_management/detail.html'

    def get(self, request, *args, **kwargs):
        arms = self.get_study().arms
        # if only a single arm exists in the study redirect to this arm directly.
        if arms.count() == 1:
            return redirect('study_management:arm-detail', pk=self.get_study_pk(), arm_pk=arms.first().pk)
        return super().get(request, *args, **kwargs)


class StudyArmDetailView(LoginRequiredMixin, StudyDetailMixin, TemplateView):
    template_name = 'study_management/arm_detail_tab_base.html'

    def get_template_names(self) -> list[str]:
        tab = self.request.GET.get('tab', 'files')
        if tab == 'files':
            return ['study_management/arm_detail_tab_files.html']
        return ['study_management/arm_detail_tab_tilesets.html']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['arm'] = get_object_or_404(StudyArm, pk=self.kwargs.get('arm_pk'), study_id=self.kwargs.get('pk'))
        ctx['current_tab'] = self.request.GET.get('tab', 'files')
        return ctx


class StudyArmTabTilesetsDetailView(LoginRequiredMixin, StudyDetailMixin, TemplateView):
    template_name = 'study_management/arm_detail_tab_tilesets.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['arm'] = get_object_or_404(StudyArm, pk=self.kwargs.get('arm_pk'), study_id=self.kwargs.get('pk'),
                                       study__created_by=self.request.user.profile)
        ctx['current_tab'] = 'tilesets'
        return ctx


class StudyArmTabFilesExportView(LoginRequiredMixin, View):

    def post(self, request, **kwargs):
        open_csv_in_browser = 'export_browser' in request.POST
        arm_pk = kwargs.get('arm_pk')
        arm = StudyArm.objects.get(pk=arm_pk)
        dst = f'{slugify(arm.study.name)}-{slugify(arm.name)}-{timezone.now().isoformat()}.csv'
        if not open_csv_in_browser:
            export_arm_files_to_csv.delay(arm.id_as_str, dst)
            messages.success(request, f'CSV will be exported to {dst}')
            return redirect('study_management:arm-detail', pk=arm.study.pk, arm_pk=arm.pk)

        # https://docs.djangoproject.com/en/5.0/howto/outputting-csv/
        class Echo:
            def write(self, value):
                return value

        writer = csv.writer(Echo())
        return StreamingHttpResponse(
            (writer.writerow(row) for row in
             itertools.chain([EXPORT_ARM_FILES_COLUMNS], export_arm_files_column_values(arm.pk))),
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{arm.study.name}-{arm.name}-{timezone.now().isoformat()}.csv"'},
        )


class StudyArmTabCasesDetailView(LoginRequiredMixin, StudyDetailMixin, TemplateView):
    template_name = 'study_management/arm_detail_tab_cases.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['arm'] = get_object_or_404(StudyArm, pk=self.kwargs.get('arm_pk'), study_id=self.kwargs.get('pk'),
                                       study__created_by=self.request.user.profile)
        ctx['current_tab'] = 'cases'
        return ctx


class StudyArmCreateImportFolderView(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, View):

    def post(self, request, **kwargs):
        arm = StudyArm.objects.get(pk=self.get_study_arm_pk(), study=self.get_study_pk())
        files = arm.files.filter(imported=False)
        if files.count() == 0:
            messages.warning(request, 'All files already imported. Aborting action.')
        else:
            i_f = ImportFolder.create_for_study_arm(arm)
            messages.success(request,
                             f'Import folder created. Copy files into {i_f.path} and remove .ignore suffix to start the import.')
        # TODO referer may not be set. figure out another way
        return redirect(request.META['HTTP_REFERER'])


class ExportImportedFilesAsCSV(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, View):
    def post(self, request, **kwargs):
        study = get_object_or_404(Study, pk=self.get_study_pk())
        arm = get_object_or_404(StudyArm, pk=self.get_study_arm_pk(), study=study)
        out = f'{slugify(study.name)}-{slugify(arm.name)}-{datetime.datetime.now()}.csv'
        export_imported_files_to_csv.delay(arm.id_as_str, out)
        messages.success(request, f'Files will be exported to {out}.')
        return redirect('study_management:arm-detail', pk=study.pk, arm_pk=arm.pk)


class CreateCaseView(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, SuccessMessageMixin, CreateView):
    form_class = CaseForm
    template_name = 'study_management/create_case.html'
    success_message = 'Case created successfully.'

    def form_valid(self, form):
        R = super().form_valid(form)
        form.instance.identifier = identifier.create_random('case')
        form.instance.created_by = self.request.user.profile
        form.instance.origin = self.request.user.profile
        form.instance.save()
        return R

    def get_success_url(self):
        return reverse('study_management:add-file-to-case',
                       kwargs=dict(
                           pk=self.get_study_pk(),
                           arm_pk=self.get_study_arm_pk(),
                           case_pk=self.object.id_as_str)
                       )


# class Add

@login_required
def add_files_to_case_form_view(request, pk, arm_pk, case_pk):
    case = Case.objects.get(pk=case_pk)
    study_arm = StudyArm.objects.get(pk=arm_pk)
    ctx = {'case': case}
    form_kwargs = {
        'queryset': case.files.order_by('-date_created'),
        'form_kwargs': dict(case=case, study_arm=study_arm, created_by=request.user.profile)}
    if request.method == 'POST':
        formset = AddFileFormSet(request.POST, **form_kwargs)
        if formset.is_valid():
            for form in formset.forms:
                # ignore forms that don't have a file name
                if len(form.cleaned_data.get('name', '').strip()) == 0 and form.cleaned_data.get('id') is None:
                    continue

                # delete file if delete is checked.
                if form.cleaned_data.get('DELETE', False) and 'id' in form.cleaned_data:
                    # delete
                    form.cleaned_data['id'].delete()
                    messages.success(request, f'File {form.cleaned_data["id"]} successfully deleted.')
                    continue
                form.save()
                form.instance.codes.clear()
                for term in form.cleaned_data.get('term_ids', []):
                    form.instance.codes.add(term)

                # only set original_path and filename for newly added files.
                if form.cleaned_data.get('id') is None:
                    form.instance.original_path = form.cleaned_data.get('name')
                    form.instance.original_filename = form.cleaned_data.get('name')

                form.instance.save()

            messages.success(request, 'Files created successfully.')

            # create new formset to delete the provided data.
            # provide queryset again to remove or add altered files
            form_kwargs['queryset'] = case.files.order_by('-date_created')
            formset = AddFileFormSet(**form_kwargs)
    else:
        formset = AddFileFormSet(**form_kwargs)

    ctx['helper'] = AddFileFormSetHelper()
    ctx['formset'] = formset
    ctx['study'] = get_object_or_404(Study, pk=pk)
    ctx['study_arm'] = get_object_or_404(StudyArm, pk=arm_pk)

    return render(request, 'study_management/add_file_to_case.html', ctx)


class CaseFileTableView(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, TemplateView):
    template_name = 'study_management/case-file-table.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        arm = ctx['arm']
        ctx['files'] = arm.files.filter(case_id=self.request.GET.get('case', None))
        return ctx


class StudyCreateView(LoginRequiredMixin, FormView):
    template_name = 'study_management/create_study.html'
    form_class = StudyForm

    def get_success_url(self) -> str:
        return reverse('study_management:arm-detail', kwargs=dict(pk=self.object.pk, arm_pk=self.study_arm.pk))

    def form_valid(self, form):
        self.object = form.save(**(dict(created_by=self.request.user.profile)))
        self.study_arm = StudyArm.objects.create(name=self.object.name, study=self.object)
        return super().form_valid(form)


class DeleteCaseView(LoginRequiredMixin, View):

    def post(self, request, pk, arm_pk, **kwargs):
        data = request.POST
        case_ = data['case']
        if StudyArm.objects.get(study_id=pk, pk=arm_pk).files.filter(case_id=case_).exists():
            Case.objects.get(pk=case_).delete()
        messages.success(request, 'Case deleted.')
        return redirect('study_management:arm-detail', pk=pk, arm_pk=arm_pk)


class TableActionView(BaseTableActionView):
    model = File

    def get_success_url(self) -> str:
        return self.request.META.get('HTTP_REFERER')

    def action(self, **kwargs):
        qs = self.get_queryset()
        data = self.request.POST
        if data.get('remove_files') is not None:
            for f in qs:
                f.remove_file()
            messages.success(self.request, f'{qs.count()} file(s) removed.')

        if data.get('delete_metadata') is not None:
            messages.warning(self.request, 'TODO implement')


class UpdateView(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, FormView):
    template_name = 'study_management/update.html'
    form_class = UpdateForm

    def get_form_kwargs(self, **kwargs):
        ctx = super().get_form_kwargs(**kwargs)
        ctx['study'] = self.get_study()
        ctx['arm'] = self.get_study_arm_pk()
        return ctx

    def form_valid(self, form):
        data = form.cleaned_data
        csv_file: UploadedFile = data.get('file')
        dest: Path = settings.TMP_DIR / str(uuid.uuid4())
        Path(csv_file.file.name).rename(dest)
        run_metadata_updater.delay(str(dest.resolve()))  # TODO .delay

        messages.success(self.request, 'Files will be updated in background. This may take a while.')
        return redirect(reverse('study_management:detail', kwargs=dict(pk=self.get_study_pk())))
