import json
import logging
from pathlib import Path
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import FormView, DetailView

import apps.storage.utils
from apps.project.import_data import forms
from apps.project.import_data.forms import AddDataToProjectForm, ImportAnnotationFromExactForm
from apps.project.import_data.tasks import import_csv, get_query, import_from_query
from apps.project.models import Project, ProjectExtraData
from apps.project.views import ProjectContextMixin
from apps.share.share_token.token_utils import parse_token, TokenInvalid
from apps.storage.extra_data.models import ExtraData
from apps.storage.models import File
from apps.storage.storage_importer.models import ImportJob


class BaseImportView(LoginRequiredMixin, FormView):

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'project': self.get_project()
        })
        return ctx

    def get_project(self):
        pk = self.kwargs.get('pk', None)
        try:
            return Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            raise Http404(f'Project with id {pk} not found.')

    def get_success_url(self):
        return self.get_project().get_absolute_url()

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw.update(dict(project=self.get_project()))
        return kw


class ImportDataView(BaseImportView):
    template_name = 'project/import_data/csv.html'
    form_class = forms.ImportDataForm

    def form_valid(self, form):
        messages.success(self.request, 'Data will be imported.')

        file = form.cleaned_data['file']
        dst = apps.storage.utils.move_to_tmp_dir(Path(file.temporary_file_path()))
        # chain celery tasks here. first import files into storage, then import into project
        project_id = self.get_project().id_as_str
        task = import_csv.delay(str(dst.resolve()), project_id)
        # task = run_metadata_importer.apply_async(
        #     kwargs={'project_id': project_id, 'profile_id': self.request.user.profile.id_as_str, 'file_path': str(dst.resolve())},
        #     link=import_files_into_project.s(project_id))

        return redirect('project:detail', pk=project_id)


class ImportJobView(LoginRequiredMixin, DetailView):
    template_name = 'project/import_data/import_job.html'

    def get_object(self, **kwargs):
        return get_object_or_404(ImportJob, celery_task_id=self.kwargs.get('celery_task_id', None),
                                 project_id=self.kwargs.get('pk', None))


class ImportFromNodeView(BaseImportView):
    template_name = 'project/import_data/import_from_node.html'
    form_class = forms.ImportFromNodeForm

    def form_valid(self, form):
        try:
            parse_token(form.cleaned_data['code'])
        except TokenInvalid:
            form.add_error('code', 'Code is invalid.')
            return self.form_invalid(form)

        messages.success(self.request, 'Data will be imported.')
        # TODO start importing the code and redirect to import job page.
        return redirect(self.request.META['HTTP_REFERER'])


class AddDataToProjectQueryView(LoginRequiredMixin, ProjectContextMixin, FormView):
    form_class = AddDataToProjectForm
    template_name = 'project/import_data/add-data-query.html'

    def get_form_kwargs(self) -> dict[str, Any]:
        kw = super().get_form_kwargs()
        kw['user'] = self.request.user.profile
        kw['project'] = self.get_project()
        return kw

    def form_invalid(self, form):
        ctx = {'errors': form.errors}
        return render(self.request, 'project/import_data/add-data-query-error.html', ctx)

    def form_valid(self, form):
        data = form.cleaned_data
        # if button_import not in: this is a htmx request.
        # if button_import is in: no htmx request.

        study_pk = data['study'].pk if data['study'] is not None else None
        term_ids = list(data['term_ids'].values_list('pk', flat=True))
        current_user = self.request.user.profile
        qs = get_query(current_user, study_pk, term_ids)

        if 'button_import' not in form.data:
            ctx = {'cases': qs}
            return render(self.request, 'project/import_data/add-data-query-preview.html', ctx)

        import_from_query.delay(current_user.id_as_str, self.get_project_id(), study_pk, term_ids)
        return render(self.request, 'project/import_data/add-data-query-close.html')

class ImportAnnotationsFromExactView(LoginRequiredMixin, ProjectContextMixin, FormView):
    form_class = ImportAnnotationFromExactForm
    template_name = 'project/import_data/exact.html'

    def get_form_kwargs(self) -> dict[str, Any]:
        kw = super().get_form_kwargs()
        kw['user'] = self.request.user.profile
        kw['project'] = self.get_project()
        return kw

    # def form_invalid(self, form):
    #     ctx = {'errors': form.errors}
    #     return render(self.request, 'project/import_data/add-data-query-error.html', ctx)

    def form_valid(self, form):
        # TODO import annotations as ExtraData. Assign to current user. How about coordinates??
        file = form.cleaned_data.get('file')
        # with file.open('r') as f:
        #     lines = f.readlines()

        application_identifier = 'exact'
        skipped = 0
        errors = []
        profile = self.request.user.profile
        project = self.get_project()

        for line in file:
            line = line.decode("utf-8").strip()
            if len(line.strip()) == 0:
                continue
            line = line.replace('],]', ']]').replace("None", "null")

            try:
                feature = json.loads(line)
            except json.decoder.JSONDecodeError as e:
                logging.exception(e)
                logging.error(f'Line is: {line}')
                errors.append(f'Error in json for line: {line}')
                skipped += 1
                continue

            properties = feature.get('properties')
            filename = properties.get('file')
            id = properties.get('id')
            annotation_type = properties.get('annotation_type')

            file_qs = File.objects.filter(name=filename)
            if not file_qs.exists():
                logging.warning(f'No file for {filename} found.')
                skipped += 1
                errors.append(f'No file for {filename} found.')
                continue

            # const transformedCoordinates = geojson.geometry.coordinates.map(coord => {
            #     // Assuming coord is [longitude, latitude] and you need to adjust for pixel coordinates
            #     const x = coord[0]; // X coordinate (in pixels, typically)
            #     const y = -coord[1]; // Transform Y to fit the image coordinate system
            #
            #     return [x, y];
            #    });
            feature['geometry']['coordinates'] = [list(map(lambda coords: [coords[0], -coords[1]], feature['geometry']['coordinates'][0]))]

            file = file_qs.first()

            # check if this annotation is already existing. if so, then update instead of create
            ed_qs = ExtraData.objects.filter(file=file,
                                             origin=profile,
                                             created_by=profile,
                                             data__features__0__properties__id=id,
                                             application_identifier=application_identifier)
            if not ed_qs.exists():
                ed = ExtraData.objects.create(
                    file=file,
                    data=feature,
                    application_identifier=application_identifier,
                    origin=profile,
                    created_by=profile,
                    description=f'{annotation_type} ({id})'
                )
                ProjectExtraData.objects.create(
                    project=project,
                    extra_data=ed,
                    imported=True, # this annotation is always imported into the project for the current user
                    user=profile
                )
                logging.debug(f'Create new annotation with id {id}')
            else:
                ed_qs.update(data=feature)
                logging.debug(f'Updating annotation with id = {id}')

        ctx = super().get_context_data(**{})
        ctx.update({
            'errors': errors,
            'skipped': skipped
        })

        return render(self.request, 'project/import_data/exact.html', ctx)
