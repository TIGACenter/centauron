import io
import uuid

import pandas
from django.db import models
from django.utils import timezone

from apps.computing.computing_executions.models import ComputingJobExecution
from apps.core import db_utils
from apps.core.models import IdentifieableMixin, Base, OriginMixin
from apps.storage.models import File
from apps.user.user_profile.models import Profile


class ComputingJobResult(IdentifieableMixin, OriginMixin, Base):
    pass


class ComputingJobArtifact(ComputingJobResult):
    computing_job = models.ForeignKey(ComputingJobExecution, on_delete=models.CASCADE, related_name='artifacts')
    file = models.ForeignKey('storage.File', on_delete=models.CASCADE, related_name='computing_job_artifacts')

    def __str__(self):
        return self.file.name

    @staticmethod
    def import_artefact(**kwargs):
        created_by: Profile | None = kwargs.get('created_by', None)
        artefacts = kwargs.get('artefacts', [])
        submission_id = kwargs.get('submission_id')
        if len(artefacts) == 0:
            return
        # computingresult
        # date_created, last_modified, id, identifier, origin
        df = pandas.read_csv(io.StringIO(artefacts))
        now = timezone.now().isoformat()
        df = df.rename(columns={'file': 'file_id', 'computing_job': 'computing_job_id'})
        file_cache = {}
        cj_cache = {}

        def fn(e):
            if e not in file_cache:
                file_cache[e] = File.objects.get_by_identifier(e).id_as_str
            return file_cache.get(e)

        df['file_id'] = df['file_id'].apply(fn)

        def fn_cj(e):
            if e not in cj_cache:
                cj_cache[e] = ComputingJobExecution.objects.filter(identifier=e, definition__submission_id=submission_id).first().id_as_str
            return cj_cache.get(e)

        df['computing_job_id'] = df['computing_job_id'].apply(fn_cj)

        df['id'] = df.apply(lambda e: str(uuid.uuid4()), axis=1)
        df['origin_id'] = created_by.id_as_str
        df['date_created'] = now
        df['last_modified'] = now

        df_cr = df[['date_created', 'last_modified', 'id', 'identifier', 'origin_id']]
        db_utils.insert_with_copy_from_and_tmp_table(df_cr, ComputingJobResult.objects.model._meta.db_table)

        df_ca = df[['id', 'computing_job_id', 'file_id']].rename(columns={'id': 'computingjobresult_ptr_id'})
        # computingartifact
        # ptr, computing_job_id, file_id
        db_utils.insert_with_copy_from_and_tmp_table(df_ca, ComputingJobArtifact.objects.model._meta.db_table)
        return list(df['id'])
