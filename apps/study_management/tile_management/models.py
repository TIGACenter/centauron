import csv
import uuid
from functools import partial

import yaml
from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.urls import reverse
from rest_framework.authtoken.models import Token

from apps.computing.models import ComputingJobDefinition
from apps.core import identifier
from apps.core.models import BaseResource, CreatedByMixin, OriginMixin, IdentifieableMixin
from apps.share.models import ShareableMixin
from apps.storage.fileset.models import FileSet
from apps.storage.models import File
from apps.study_management.models import StudyArm
from apps.terminology.models import Code


class TileSet(ShareableMixin, FileSet):
    class Status(models.TextChoices):
        IDLE = 'idle'
        IMPORTING = 'importing'
        COPYING = 'copying'
        LOCKED = 'locked'

    status = models.CharField(default=Status.IDLE, choices=Status.choices, max_length=10)
    terms = models.ManyToManyField('terminology.Code', blank=True, related_name='tilesets')
    study_arm = models.ForeignKey('study_management.StudyArm', on_delete=models.CASCADE, related_name='tilesets')
    computing_job = models.ForeignKey('computing.ComputingJobDefinition',
                                      related_name='filesets',
                                      on_delete=models.SET_NULL,
                                      null=True,
                                      blank=True)
    # those are the files from which the tiles in this set originate from
    included_files = models.ForeignKey('fileset.FileSet', on_delete=models.CASCADE,
                                       related_name='tilesets', null=True,
                                       blank=True)
    tiling_params = models.JSONField(default=dict, blank=True)
    source = models.ForeignKey('tile_management.TileSet', on_delete=models.SET_NULL,
                               blank=True, null=True, related_name='copies')

    @property
    def is_copy(self):
        return self.source is not None

    @property
    def is_locked(self):
        return self.status == TileSet.Status.LOCKED

    @property
    def is_idle(self):
        return self.status == TileSet.Status.IDLE

    @property
    def included_terms(self):
        concept_pks = self.files.values_list('codes', flat=True).distinct()
        return Code.objects.filter(id__in=concept_pks)

    def set_status(self, status):
        self.status = status
        self.save(update_fields=['status'])

    def get_absolute_url(self):
        return reverse('study_management:tile_management:detail',
                       kwargs=(dict(pk=self.study_arm.study_id, arm_pk=self.study_arm.pk, tileset_pk=self.pk)))

    def copy(self):
        ts = TileSet.objects.create(name=f'{self.name} (copy)',
                                    created_by=self.created_by,
                                    origin=self.origin,
                                    study_arm=self.study_arm,
                                    source=self,
                                    included_files=self.included_files,
                                    identifier=identifier.create_random('tileset'))
        # TODO copy rest in celery task
        from apps.study_management.tile_management.tasks import copy_tileset

        transaction.on_commit(partial(copy_tileset.delay, self.id_as_str, ts.id_as_str))
        return ts

    @staticmethod
    def query_files(arm: StudyArm, terms: list[Code], imported: bool = True):
        term_filter = None
        for t in terms:
            if term_filter is None:
                term_filter = Q(codes=t)
            else:
                term_filter = term_filter & Q(codes=t)
            # term_filter['concepts'] = t
        files = File.objects.filter(case__in=arm.cases.all(), imported=imported)
        if term_filter is not None:
            files = files.filter(term_filter)
        files = files.distinct().prefetch_related('case')
        return files

    @staticmethod
    def create(created_by, name, arm, yml):
        yml = yaml.safe_load(yml)
        data = yml['data']
        terms = []
        imported = True
        args = yml.get('args', {})
        if isinstance(data, dict):
            filter = data.get('filter', {})
            filter_terms_raw = filter.get('terms', '').split(',')
            filter_terms_raw = [t.split('#') for t in filter_terms_raw]
            terms = [Code.objects.get(created_by=created_by, ontology__uri=t[0], code=t[1]) for t in filter_terms_raw]
            imported = filter.get('imported', True)

        script = yml.get('script')
        if isinstance(script, str):
            script = [script]

        # create the original fileset
        fs: FileSet = FileSet.objects.create(name=f'original files for {name}')
        files = TileSet.query_files(arm, terms, imported)

        if files.count() == 0:
            raise ValueError('No files found.')

        fs.files.set(files)
        # create the tileset
        ts: TileSet = TileSet.objects.create(name=name,
                                             study_arm=arm,
                                             created_by=created_by,
                                             origin=created_by,
                                             included_files=fs,
                                             identifier=identifier.create_random('tileset'))
        ts.terms.set(terms)

        # TODO refactor and split in different methods
        # create data file for the computing job
        data_file = str(uuid.uuid4())
        with (settings.STORAGE_DATA_DIR / data_file).open('w') as f:
            writer = csv.DictWriter(f, fieldnames=['original_filename', 'path', 'identifier'], delimiter=';')
            writer.writeheader()
            for file in files:
                writer.writerow(dict(original_filename=file.original_filename,
                                     path=file.path,
                                     identifier=str(file.identifier)))

        cjd = ComputingJobDefinition.objects.create(
            created_by=created_by,
            origin=created_by,
            identifier=identifier.create_random('computing-job-definition'),
            entrypoint=script,
            namespace='default',
            docker_image=yml.get('image'),
            name=f'Tiling {ts.name}',
            data_file=data_file,
            output=['*'],
            args=args,
            environment_variables=dict(API_SECRET=Token.objects.update_or_create(user=created_by.user)[0].key,
                                       API_ADDRESS=settings.EXTERNAL_ADDRESS + 'api/',
                                       STUDY=arm.study.id_as_str,
                                       TILESET=ts.id_as_str),
            environment_variables_job_context=dict(filesets=ts.id_as_str)
        )
        ts.computing_job = cjd
        ts.save(update_fields=['computing_job'])
        # start computing job definition
        transaction.on_commit(partial(cjd.execute, created_by.id_as_str))
        # cjd.execute(created_by.id_as_str)

        return ts

    def __str__(self):
        return f'{self.name} ({self.study_arm.name})'

    def create_share(self, project_identifier, valid_from, valid_until, from_, to, file_query):
        from apps.study_management.tile_management.tasks import create_tileset_share
        create_tileset_share.delay(self.id_as_str,
                                   project_identifier,
                                   valid_from,
                                   valid_until,
                                   from_,
                                   to,
                                   file_query)
