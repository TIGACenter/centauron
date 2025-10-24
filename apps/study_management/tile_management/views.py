import shutil
import uuid
from datetime import timedelta
from functools import partial
from typing import Any

import yaml
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import TemplateView, FormView
import logging
from apps.storage.storage_exporter.tasks import export_files
from apps.study_management.import_data import tasks
from apps.study_management.import_data.models import ImportJob
from apps.study_management.models import StudyArm
from apps.study_management.tile_management.forms import ImportCSVForm, UpdateForm, ShareTileSetForm
from apps.study_management.tile_management.models import TileSet
from apps.study_management.tile_management.tasks import export_tileset_as_csv, export_tileset_as_csv_writer, \
    update_tileset, create_tileset_share
from apps.study_management.views import StudyDetailMixin, StudyArmDetailMixin
from apps.terminology.models import Code


class CreateTileSetView(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, TemplateView):
    template_name = 'study_management/tile_management/create.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['terms'] = ctx['study'].terms.all()
        return ctx

    def post(self, request, **kwargs):
        name = request.POST.get('name')
        arm = get_object_or_404(StudyArm, pk=kwargs.get('arm_pk'), study_id=kwargs.get('pk'),
                                study__created_by=request.user.profile)

        yml = request.POST.get('yml')
        # TODO use a FormView here so errors can be thrown and shown and bla bla
        '''
image: docker.cytoslider.com/centauron/tiler:latest
args:
  size: 128
  step: 0
  resolution: 40
data:
  filter:
    terms: uri#abc,uri#123,uri#qwer,uri#val # CSV are AND condition
    imported: true
output: # output of the computation that needs to be saved (for download or use in later stages)
  - "*"
resources:
  requests:
    memory: 20G
        '''

        # tile_size = int(request.POST.get('tile_size'))
        # step_size = int(request.POST.get('step_size'))
        # tile_resolution = int(request.POST.get('tile_resolution'))

        # create fileset and job and stuff
        user = self.request.user.profile
        try:
            ts = TileSet.create(user, name, arm, yml)
            return redirect(ts)
        except ValueError as e:
            logging.error(e)
            messages.error(request, f'Error: {e}')

        return redirect(request.META['HTTP_REFERER'])


class CreateTileSetFilterView(LoginRequiredMixin, View):
    def post(self, request, **kwargs):
        arm = get_object_or_404(StudyArm, pk=kwargs.get('arm_pk'), study_id=kwargs.get('pk'),
                                study__created_by=request.user.profile)

        yml = yaml.safe_load(request.POST.get('yml'))
        if yml is None:
            return render(request, 'study_management/tile_management/filter_error.html',
                          {'error': 'No yml provided.'})
        data = yml['data']
        terms = []
        imported = True
        if isinstance(data, dict):
            filter = data.get('filter', {})
            filter_terms_raw = filter.get('terms', '').split(',')
            filter_terms_raw = [t.split('#') for t in filter_terms_raw]
            try:
                terms = [Code.objects.get(created_by=self.request.user.profile,
                                             ontology__uri=t[0],
                                             code=t[1]) for t in filter_terms_raw]
            except Code.DoesNotExist as e:
                return render(request, 'study_management/tile_management/filter_error.html', {'error': str(e)})
            imported = filter.get('imported', True)

        files = TileSet.query_files(arm, terms, imported=imported)
        n = 10
        ctx = {
            'number_of_slides': files.count(),
            'files': files[:n],
            'n': n
        }
        return render(request, 'study_management/tile_management/filter.html', ctx)


class FileSetDetailView(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, TemplateView):
    template_name = 'study_management/tile_management/detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tileset = get_object_or_404(TileSet, created_by=self.request.user.profile, pk=self.kwargs.get('tileset_pk'))
        ctx['object'] = tileset
        ctx['computing_job'] = tileset.computing_job
        return ctx


class ExportView(LoginRequiredMixin, View):

    def post(self, request, **kwargs):
        tileset = TileSet.objects.get(created_by=self.request.user.profile, pk=self.kwargs.get('tileset_pk'))
        identifiers = list(tileset.files.values_list('identifier', flat=True))
        dst = f'{slugify(tileset.name)}-{timezone.now()}'
        export_files.delay(dst, identifiers)
        messages.success(request, f'Files will be exported into {dst} in background.')
        return redirect(request.META['HTTP_REFERER'])


class CreateByFileUpload(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, FormView):
    template_name = 'study_management/tile_management/create_file_upload.html'
    form_class = ImportCSVForm

    def get_success_url(self) -> str:
        return reverse('study_management:import_data:detail',
                       kwargs=dict(pk=self.kwargs.get('pk'), arm_pk=self.kwargs.get('arm_pk'), job_pk=self.object.pk))

    def form_valid(self, form):
        data = form.cleaned_data
        tmp_name = data['file'].file.name
        dst = settings.TMP_DIR / str(uuid.uuid4())
        shutil.move(tmp_name, dst)
        # job = ImportJob()
        # job.created_by = self.request.user.profile
        tileset = TileSet.objects.create(created_by=self.request.user.profile,
                                         study_arm_id=self.kwargs.get('arm_pk'),
                                         name=data.get('name'))
        job = ImportJob.objects.create(
            created_by=self.request.user.profile,
            study_arm_id=self.kwargs.get('arm_pk'),
            file=str(dst.relative_to(settings.TMP_DIR)))
        self.object = job
        transaction.on_commit(partial(tasks.run_importer_tileset, job.id_as_str, tileset.id_as_str))
        messages.success(self.request, 'Data will be imported in background.')
        return redirect(job)


class ExportCSV(LoginRequiredMixin, View):

    def post(self, request, pk, arm_pk, tileset_pk):
        tileset = TileSet.objects.get(created_by=self.request.user.profile,
                                      pk=tileset_pk)
        columns = request.POST.getlist('columns')

        # if more than 100k files in tileset export into export folder. otherwise download.
        if tileset.files.count() > 100_000:
            export_tileset_as_csv.delay(tileset.id_as_str, columns)
            messages.success(request, 'Tileset CSV will be exported into export folder.')
            return redirect('study_management:tile_management:detail', **self.kwargs)

        # proceed to download file
        # https://docs.djangoproject.com/en/4.2/howto/outputting-csv/
        class Echo:
            def write(self, value):
                return value

        return StreamingHttpResponse(
            (export_tileset_as_csv_writer(columns, tileset, Echo())),
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{slugify(tileset.name)}.csv"'},
        )


class UpdateView(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, FormView):
    template_name = 'study_management/tile_management/dialog_update.html'
    form_class = UpdateForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tileset = get_object_or_404(TileSet, created_by=self.request.user.profile, pk=self.kwargs.get('tileset_pk'))
        ctx['object'] = tileset
        return ctx

    def form_valid(self, form):
        data = form.cleaned_data
        messages.success(self.request, 'TileSet will be updated in background.')
        tileset = TileSet.objects.get(pk=self.kwargs.get('tileset_pk'), created_by=self.request.user.profile)
        csv_path = settings.TMP_DIR / str(uuid.uuid4())
        shutil.move(data['file'].file.name, csv_path)
        update_tileset.delay(tileset.id_as_str, str(csv_path.relative_to(settings.TMP_DIR)))  # TODO .delay

        return redirect('study_management:tile_management:detail', **self.kwargs)


class CopyView(LoginRequiredMixin, View):

    def post(self, request, pk, arm_pk, tileset_pk, **kwargs):
        messages.success(request, 'Tileset will be copied in background.')

        ts_org = TileSet.objects.get(pk=tileset_pk, created_by=request.user.profile)
        ts = ts_org.copy()

        return redirect(ts)


class LockView(LoginRequiredMixin, View):

    def post(self, request, pk, arm_pk, tileset_pk, **kwargs):
        ts = TileSet.objects.get(pk=tileset_pk, created_by=request.user.profile)
        if not ts.is_idle and not ts.is_locked:
            messages.error(request, f'TileSet must be idle or locked to (un)lock.')
            return redirect(ts)
        new_state = TileSet.Status.LOCKED if ts.is_idle else TileSet.Status.IDLE
        ts.set_status(new_state)
        messages.success(request, f'Tileset is now {ts.status}.')

        return redirect(ts)


class ShareView(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, FormView):
    template_name = 'study_management/tile_management/share.html'
    form_class = ShareTileSetForm

    def get_tileset(self):
        return get_object_or_404(TileSet, pk=self.kwargs.get('tileset_pk'), created_by=self.request.user.profile)

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        tileset = self.get_tileset()
        c.update({
            'object': tileset,
            'codes': [dict(**e, id=str(e['pk'])) for e in tileset.included_terms.values('pk', 'codes__codesystem__name', 'codes')]
        })
        return c

    def get_initial(self) -> dict[str, Any]:
        ctx = {
            'valid_from': timezone.now(),
            'valid_until': timezone.now() + timedelta(days=30)
        }
        if not settings.DEBUG:
            return ctx
        # ctx['project_identifier'] = identifier.create_random('project')
        ctx['project_identifier'] = 'ak.dev.centauron.io#project::abc'

        return ctx

    def form_valid(self, form):
        data = form.cleaned_data
        node = data.get('node')
        project_identifier = data.get('project_identifier')
        messages.success(self.request, f'Data will be shared with {node} in background.')
        create_tileset_share(self.get_tileset().id_as_str,
                             project_identifier,
                             data.get('valid_from'),
                             data.get('valid_until'),
                             self.request.user.profile.id_as_str,
                             node.id_as_str)

        return redirect(self.request.META['HTTP_REFERER'])
