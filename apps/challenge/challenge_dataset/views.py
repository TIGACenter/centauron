import csv
import itertools
import json
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import DetailView as DjangoDetailView, CreateView as DjangoCreateView, FormView, UpdateView

from apps.blockchain.messages import AddMessage, Object
from apps.blockchain.models import Log
from apps.challenge.challenge_dataset import forms
from apps.challenge.challenge_dataset.forms import QueryForm
from apps.challenge.challenge_dataset.models import Dataset
from apps.challenge.challenge_dataset.tasks import import_csv
from apps.challenge.views import BaseTabView, ChallengeContextMixin
from apps.core import identifier
from apps.core.views import BaseTableActionView
from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.storage.utils import move_to_tmp_dir
from apps.terminology.models import Code


class DatasetContextMixin(ChallengeContextMixin):

    def get_dataset_id(self) -> UUID | None:
        return self.kwargs.get('dataset_pk')

    def get_dataset(self) -> Dataset:
        return Dataset.objects.filter(challenge_id=self.get_challenge_id()).get(pk=self.get_dataset_id())

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['dataset'] = self.get_dataset()
        return ctx


class ListView(BaseTabView):
    template_name = 'challenge/challenge_dataset/tab.html'

    def get_tab_name(self):
        return 'datasets'


class CreateView(LoginRequiredMixin, ChallengeContextMixin, DjangoCreateView):
    template_name = 'challenge/challenge_dataset/create.html'
    form_class = forms.DataSetCreateForm

    def get_queryset(self):
        return Dataset.objects.filter(challenge_id=self.get_challenge_id())

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.created_by = self.request.user.profile
        obj.identifier = identifier.create_random('dataset')
        obj.challenge_id = self.get_challenge_id()
        obj.origin = self.request.user.profile
        obj.encrypted = False
        obj.is_public = True
        obj.save()
        obj.broadcast_create_event()
        return redirect(obj)


class DetailView(LoginRequiredMixin, DatasetContextMixin, DjangoDetailView):
    template_name = 'challenge/challenge_dataset/detail.html'

    def get_object(self, queryset=None):
        return self.get_dataset()


class ImportDataCSVView(LoginRequiredMixin, DatasetContextMixin, FormView):
    template_name = 'challenge/challenge_dataset/import_csv.html'
    form_class = forms.ImportDataForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'challenge': self.get_challenge()
        })
        return ctx

    def get_success_url(self):
        return self.get_dataset().get_absolute_url()

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw.update(dict(dataset=self.get_dataset()))
        return kw

    def form_valid(self, form):
        messages.success(self.request, 'Data will be imported.')
        file = form.cleaned_data['file']
        dst = move_to_tmp_dir(Path(file.temporary_file_path()))
        import_csv.delay(self.request.user.profile.id_as_str, str(dst.resolve()), self.get_dataset_id())
        messages.success(self.request, 'Files will be imported.')
        return redirect(self.get_dataset().get_absolute_url())


class ImportFromProjectView(LoginRequiredMixin, DatasetContextMixin, View):

    def post(self, request, pk, dataset_pk, **kwargs):
        query = json.loads(request.POST.get('query_filter'))
        dataset = self.get_dataset()
        dataset.import_(query['model'], query['filter'])

        messages.success(request, 'Data imported into dataset.')
        return redirect('challenge:challenge_dataset:detail', pk=pk, dataset_pk=dataset_pk)


class QueryView(LoginRequiredMixin, DatasetContextMixin, FormView):
    template_name = 'challenge/challenge_dataset/query/query.html'
    form_class = QueryForm

    def get_form_kwargs(self) -> dict[str, Any]:
        ctx = super().get_form_kwargs()
        ctx['dataset'] = self.get_dataset()
        return ctx

    def form_valid(self, form):
        data = form.cleaned_data
        case_name = data.get('case_name', '').strip()
        qs = Case.objects.filter(projects__pk=self.get_challenge().project_id, origin__in=data['nodes'])
        terms_pk = data['term_ids'].values_list('pk', flat=True)
        if terms_pk.count() > 0:
            qs = qs.filter(files__codes__in=Code.objects.filter(pk__in=terms_pk))
        if len(case_name) > 0:
            qs = qs.filter(name__iexact=case_name)
        # current_user = self.request.user.profile

        if 'button_import' not in form.data:
            ctx = {'results': qs}
            return render(self.request, 'challenge/challenge_dataset/query/results.html', ctx)

        dataset = self.get_dataset()
        dataset.cases.add(*qs.all())
        dataset.files.add(*File.objects.filter(case__in=qs))

        msg = AddMessage(
            actor=self.request.user.profile.to_actor(),
            object=Object(model="slide", value=list(qs.values_list('identifier', flat=True))),
            context={"dataset": dataset.to_identifiable(), "challenge": self.get_challenge().to_identifiable()},
        )
        Log.send_broadcast(msg)

        return render(self.request, 'challenge/challenge_dataset/query/success.html')

    def query(self, request, qs):
        ctx = {
            'results': qs
        }
        return render(request, 'challenge/challenge_dataset/query/results.html', ctx)

    def import_(self, request, pk, qs, model, query_filter):
        success = True
        ctx = {
            'success': success,
            'filter': {'filter': query_filter, 'model': model}
        }
        return render(request, 'challenge/challenge_dataset/query/import.html', ctx)

    # def post(self, request, pk, **kwargs):
    #     action_is_query = request.POST.get('import', 'query').lower() != 'import'
    #     raw_q = request.POST.get('query', '{}')
    #     if len(raw_q.strip()) == 0:
    #         raw_q = '{}'
    #     query = json.loads(raw_q)
    #     selected_model = request.POST.get('model')
    #     if selected_model == 'case':
    #         model = Case
    #     else:
    #         model = File
    #     query_filter = {'projects__id': pk, **query}
    #     try:
    #         qs = model.objects.filter(**query_filter)
    #     except ValidationError as e:
    #         logging.error(e)
    #         return render(request, 'project/../../../templates/challenge/challenge_dataset/query/error.html',
    #                       {'message': str(e)})
    #
    #     if action_is_query:
    #         return self.query(request, qs)
    #     else:
    #         return self.import_(request, pk, qs, selected_model, query_filter)

class FileTableActionView(DatasetContextMixin, BaseTableActionView):
    model = File

    def get_success_url(self) -> str:
        return self.request.META.get('HTTP_REFERER')

    def action(self, **kwargs):
        qs = self.get_queryset()
        data = self.request.POST
        if data.get('remove_files') is not None:
            self.get_dataset().remove_files(qs)
            messages.success(self.request, f'{qs.count()} file(s) removed from dataset.')

class UpdateDatasetFormView(LoginRequiredMixin, SuccessMessageMixin, DatasetContextMixin, UpdateView):
    form_class = forms.UpdateDatasetForm
    success_message = 'Dataset updated.'
    template_name = 'challenge/challenge_dataset/update.html'

    def get_object(self, queryset=None):
        return self.get_dataset()

    def get_success_url(self) -> str:
        return reverse('challenge:challenge_dataset:update', kwargs={'pk': self.get_challenge_id(), 'dataset_pk': self.object.pk})



class ExportAsCSVView(LoginRequiredMixin, DatasetContextMixin, View):

    def post(self, request, **kwargs):
        dataset = self.get_dataset()
        dst = f'{slugify(dataset.name)}-{timezone.now().isoformat()}.csv'

        # https://docs.djangoproject.com/en/5.0/howto/outputting-csv/
        class Echo:
            def write(self, value):
                return value

        def get_rows():
            files = dataset.files.all()
            for f in files:
                yield [f.id_as_str, f.identifier, f.case.name, f.name, f.path, f.original_path, f.original_filename,
                       f.origin.identifier, f.imported]

        FIELDS = ['id', 'identifier', 'case', 'name', 'path', 'original_path', 'original_filename', 'origin',
                  'imported']

        writer = csv.writer(Echo())
        return StreamingHttpResponse(
            (writer.writerow(row) for row in
             itertools.chain([FIELDS], get_rows())),
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{dst}"'},
        )
