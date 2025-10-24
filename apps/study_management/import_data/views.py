import shutil
import uuid
from functools import partial
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction, connection
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, DetailView, TemplateView

from apps.study_management.import_data import forms, tasks
from apps.study_management.import_data.models import ImportJob
from apps.study_management.models import StudyArm, Study
from apps.study_management.views import StudyDetailMixin, StudyArmDetailMixin
from apps.terminology.models import CodeSystem, Code


class ImportFormPreview(LoginRequiredMixin, StudyDetailMixin, StudyArmDetailMixin, View):
    template_name = 'study_management/import_data/preview.html'

    def get_import_file_content_metadata(self, file: Path):
        df = pd.read_csv(file, na_filter=False)
        total_files = len(df.index)
        df = df[['codes']].drop_duplicates()
        df['codes'] = df['codes'].apply(lambda e: e.split(','))
        terms = df.explode('codes')
        # terms = df.loc[terms['codes'].str.len() > 0]  # only rows that actually have codes

        terms_cache = {}
        codesystem_cache = {}

        def fn(c):
            codesystem_name = None
            codesystem_exists = False
            term_name = None

            if '#' not in c:
                return pd.Series(
                    data={'exists': True, 'id': 1, 'codesystem_name': codesystem_name,
                          'codesystem_uri': '',
                          'codesystem_exists': True, 'term_name': term_name,
                          'alternative_codes': ''})

            o, t = c.split('#')

            if t not in terms_cache:
                if o not in codesystem_cache:
                    qs = CodeSystem.objects.filter(uri=o)
                    codesystem_exists = qs.exists()
                    if codesystem_exists:
                        cs = qs.first()
                        codesystem_cache[cs.uri] = cs.name
                        codesystem_name = cs.name
                        codesystem_uri = cs.uri
                    else:
                        codesystem_name = o
                        codesystem_cache[o] = o
                        codesystem_uri = o
                else:
                    codesystem_name = codesystem_cache[o]
                    codesystem_exists = True
                    codesystem_uri = o

                qs = Code.objects.filter(codesystem__uri=o, code=t)
                exists = qs.exists()
                if not exists:
                    # TODO tune the distance here. 3 is enough to account for typings. 1 insert + 1 deletion + 1 extra
                    # TODO tune .3 selector
                    with connection.cursor() as cursor:
                        # alternative queries to try:
                        # f'select * from {Code.objects.model._meta.db_table} where levenshtein_less_equal(code, %s, 3) < 3'
                        limit = 0.5
                        cursor.execute(
                            f'select code, id, codesystem_name, round(l.sim::numeric, 4) from {Code.objects.model._meta.db_table},lateral ( select similarity(code, %s) as sim) l where l.sim > {limit} order by l.sim desc',
                            [t])
                        rows = cursor.fetchall()
                        alternative_codes = tuple(map(lambda e: (e[1], e[2], e[0], e[3]), rows))

                    id = None
                    # TODO cache alternative codes
                else:
                    id = qs.first().id_as_str
                    alternative_codes = ()
                term_name = t
            else:
                exists = True
                id = terms_cache[c].id_as_str
                term_name = terms_cache[c].name
                alternative_codes = ()
                codesystem_uri = o

            return pd.Series(
                data={'exists': exists, 'id': id, 'codesystem_name': codesystem_name,
                      'codesystem_uri': codesystem_uri,
                      'codesystem_exists': codesystem_exists, 'term_name': term_name,
                      'alternative_codes': alternative_codes})

        terms[['exists', 'id', 'codesystem_name', 'codesystem_uri', 'codesystem_exists', 'term_name',
               'alternative_codes']] = terms['codes'].apply(fn)
        codes = terms[['exists', 'id', 'codesystem_name', 'codesystem_uri', 'codesystem_exists', 'term_name',
                       'alternative_codes']].drop_duplicates().to_dict(
            'records')
        return total_files, codes

    def get_context_data(self, **kwargs):
        ctx = {}
        ctx['study'] = get_object_or_404(Study, pk=self.get_study_pk())
        ctx['study_arm_pk'] = self.get_study_arm_pk()
        file = Path(self.request.session.get('study-import'))
        ctx['file'] = file
        total_files, codes = self.get_import_file_content_metadata(file)
        ctx['total_files'] = total_files
        ctx['codes'] = codes
        return ctx

    def get(self, request, **kwargs):
        if request.session.get('study-import') is None:
            messages.error(request, 'No file found.')
            return redirect('study_management:import_data:form')
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, **kwargs):
        study_arm = get_object_or_404(StudyArm, pk=self.get_study_arm_pk(), study_id=self.get_study_pk())
        mapping_keys = list(filter(lambda k: k.startswith('mapping.'), request.POST.dict()))
        mapping = {}
        i = len('mapping.')
        for k in mapping_keys:
            mapping[k[i:]] = request.POST[k]
        dst = Path(request.session.pop('study-import'))
        job = ImportJob.objects.create(
            created_by=self.request.user.profile,
            study_arm=study_arm,
            file=str(dst.relative_to(settings.TMP_DIR)))
        transaction.on_commit(partial(tasks.run_importer.delay, job.id_as_str, mapping))
        messages.success(self.request, 'Data will be imported.')
        return redirect(job)


class ImportFormView(LoginRequiredMixin, StudyDetailMixin, FormView):
    form_class = forms.ImportForm
    template_name = 'study_management/import_data/form.html'

    def get_success_url(self) -> str:
        return reverse('study_management:import_data:detail',
                       kwargs=dict(pk=self.kwargs.get('pk'), arm_pk=self.kwargs.get('arm_pk'), job_pk=self.object.pk))
        # return reverse('study_management:import_data:form',
        #                kwargs=dict(pk=self.kwargs.get('pk'), arm_pk=self.kwargs.get('arm_pk')))

    def form_valid(self, form):
        # move uploaded file to centauron tmp folder
        uploaded_file = form.cleaned_data["file"]
        dst = settings.TMP_DIR / f'{uuid.uuid4()}-{uploaded_file.name}'
        shutil.move(uploaded_file.file.name, dst)
        self.request.session['study-import'] = str(dst.resolve())
        return redirect('study_management:import_data:form-preview', pk=self.kwargs.get('pk'),
                        arm_pk=self.kwargs.get('arm_pk'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'arm': get_object_or_404(StudyArm, pk=self.kwargs.get('arm_pk'), study_id=self.kwargs.get('pk'),
                                     study__created_by=self.request.user.profile)
        })
        return ctx


class ImportJobDetailView(LoginRequiredMixin, StudyDetailMixin, DetailView):
    template_name = 'study_management/import_data/detail.html'

    def get_object(self, queryset=None):
        return ImportJob.objects.get(pk=self.kwargs.get('job_pk'), study_arm_id=self.kwargs.get('arm_pk'),
                                     study_arm__study__created_by=self.request.user.profile)


class ImportJobListView(LoginRequiredMixin, StudyDetailMixin, TemplateView):
    template_name = 'study_management/import_data/list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = ImportJob.objects.filter(study_arm_id=self.kwargs.get('arm_pk')).order_by('-date_created')
        ctx['arm'] = get_object_or_404(StudyArm, pk=self.kwargs.get('arm_pk'), study_id=self.kwargs.get('pk'))
        return ctx
