import io
import logging
import uuid

import pandas
from annoying.fields import AutoOneToOneField
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone

from apps.core import db_utils
from apps.core.managers import BaseManager
from apps.core.models import Base, CreatedByMixin, OriginMixin
from apps.node.models import Node
from apps.user.user_profile.models import Profile


class CodeSystem(CreatedByMixin, OriginMixin, Base):
    name = models.CharField(max_length=200, unique=True)
    uri = models.CharField(max_length=500, unique=True)
    project = AutoOneToOneField('project.Project', null=True, blank=True, default=None, on_delete=models.CASCADE,
                                related_name='codesystem')

    def __str__(self):
        return self.uri

    @staticmethod
    def import_codesystem(**kwargs):
        data = kwargs.get('data')
        share = kwargs.get('share')
        if data is None:
            logging.info('No codesystems to import')
            return

        df = pandas.read_csv(io.StringIO(data))
        df = df.rename(columns={'origin': 'origin_id'})
        now = timezone.now().isoformat()
        df['date_created'] = now
        df['last_modified'] = now
        # df['created_by_id'] = kwargs.get('created_by').id_as_str
        df['id'] = df.apply(lambda e: str(uuid.uuid4()), axis=1)
        df = df.drop_duplicates()
        # filter out files that are already existing in database
        identifiers = df['uri'].to_list()
        qs = CodeSystem.objects.filter(uri=identifiers).distinct()
        existing_codesystems = {e[0]: e[1] for e in qs.values_list('uri', 'id')}
        existing_rows = df['uri'].isin(existing_codesystems.keys())
        df['existing'] = existing_rows

        def fn_set_id(e):
            if not e['existing']: return str(uuid.uuid4())
            return existing_codesystems[e['uri']]

        df['id'] = df.apply(fn_set_id, axis=1)

        df_id = df[['id']]

        profile_cache = {}

        def fn(e):
            if not pandas.isna(e) and e not in profile_cache:
                p, _ = Profile.objects.get_or_create(identifier=e)
                profile_cache[e] = p.id_as_str
            return profile_cache.get(e)

        df['origin_id'] = df['origin_id'].apply(fn)

        # filter out existing files
        df = df[~existing_rows]
        df = df.drop(columns=['existing'])
        logging.info(df)
        logging.info(df.index)
        db_utils.insert_with_copy_from_and_tmp_table(df, CodeSystem.objects.model._meta.db_table)

        # FIXME this is not working correctly
        # if share is not None:
        #     if len(df.index) > 0:
        #         df_id['share_id'] = share.id_as_str
        #         df_id = df_id.rename(columns={'id': 'codesystem_id'})
        #         from apps.share.models import Share
        #         db_utils.insert_with_copy_from_and_tmp_table(df_id, Share.codesystem.through.objects.model._meta.db_table,
        #                                                      insert_columns='codesystem_id, share_id')


class CodeManager(BaseManager):

    def get_by_code_and_codesystem(self, code, codesystem):
        return self.get(code=code, codesystem__uri=codesystem)


class Code(CreatedByMixin, OriginMixin, Base):
    objects = CodeManager()

    class Meta:
        constraints = [
            UniqueConstraint(fields=['codesystem', 'code', 'created_by'], name='unique_code_per_user')
        ]

    codesystem = models.ForeignKey(CodeSystem, on_delete=models.CASCADE, related_name='codes')
    code = models.CharField(max_length=500)
    human_readable = models.CharField(max_length=500, blank=True, null=True)
    # denormalize for better db performance
    codesystem_name = models.CharField(max_length=500)

    def __str__(self):
        return f'{self.codesystem_name}#{self.code} ({self.human_readable})'

    def get_readable_str(self):
        if self.human_readable is not None: return self.human_readable
        return self.code

    def get_machine_rep(self) -> str:
        return f'{self.codesystem.uri}#{self.code}'

    @staticmethod
    def import_codes(**kwargs):
        # TODO check if codes get imported if they already exist.
        # TODO codes get imported multiple times.
        # TODO do not import codes that have no origin. those codes are already pre-installed.
        from apps.user.user_profile.models import Profile
        from apps.storage.models import File
        from apps.share.models import Share
        from apps.project.models import Project

        codes = kwargs.get('codes')
        if codes is None:
            return
        created_by = kwargs.get('created_by')
        origin = kwargs.get('origin')

        df = pandas.read_csv(io.StringIO(codes))
        df = df.drop(columns=['file'])
        now = timezone.now().isoformat()
        df['date_created'] = now
        df['last_modified'] = now
        # df['created_by_id'] = kwargs.get('created_by').id_as_str
        # df['id'] = df.apply(lambda e: str(uuid.uuid4()), axis=1)

        # remove codes that do not have an origin. those are codes than come pre-installed with centauron.
        # df = df.apply(lambda e: e['origin'] is not None, axis=1)
        # df = df.dropna() # TODO test if this is not dropping too much.

        # drop duplicates
        df = df.drop_duplicates()
        profile_cache = {}

        def from_profile_cache(e):
            logging.info(e)
            if isinstance(e, float) and e == 0.0 or isinstance(e, str) and len(e) == 0:
                return None
            if e not in profile_cache:
                try:
                    profile = Profile.objects.get_by_identifier(e)
                except Profile.DoesNotExist:
                    profile = Profile.objects.create_and_return(e)
                profile_cache[e] = profile.id_as_str
            return profile_cache.get(e)

        codesystem_cache = {}

        def from_codesystem_cache(e):
            e = e.codesystem_id
            if e not in codesystem_cache:
                qs = CodeSystem.objects.filter(uri=e)
                if qs.exists():
                    cs = qs.first()
                else:
                    cs = CodeSystem.objects.create(uri=e, created_by=created_by, origin=origin)
                codesystem_cache[e] = pandas.Series(data={'codesystem_id': cs.id_as_str, 'codesystem_name': cs.name})
            return codesystem_cache[e]

        # first create code system or get id
        logging.info(df)
        # then import codes
        # filter out files that are already existing in database
        qs = Code.objects.filter(code__in=df['code'].to_list(),
                                 codesystem__uri__in=df['codesystem'].to_list()).distinct()
        existing_files = {f'{e[0]},{e[1]}': e[2] for e in qs.values_list('code', 'codesystem__uri', 'id')}
        # existing_rows = df['identifier'].isin(existing_files.keys())
        existing_codes = list(map(lambda e: e.split(',')[0], existing_files.keys()))
        existing_codesystems = list(map(lambda e: e.split(',')[1], existing_files.keys()))
        existing_rows = (df['code'].isin(existing_codes) & df['codesystem'].isin(existing_codesystems))
        df['existing'] = existing_rows

        def fn_set_id(e):
            if not e['existing']: return str(uuid.uuid4())
            return existing_files[f'{e["code"]},{e["codesystem"]}']

        df['id'] = df.apply(fn_set_id, axis=1)  # df.apply(lambda e: str(uuid.uuid4()), axis=1)

        # filter out existing files
        df = df[~existing_rows]
        df = df.drop(columns=['existing'])
        # for all rows that are not existing yet.
        if len(df.index) > 0:
            df = df.rename(columns={'origin': 'origin_id', 'codesystem': 'codesystem_id'})
            # df['origin_id'] = df['origin_id'].apply(from_profile_cache) # TODO fix this.
            df[['codesystem_id', 'codesystem_name']] = df.apply(from_codesystem_cache, axis=1)
            db_utils.insert_with_copy_from_and_tmp_table(df, Code.objects.model._meta.db_table)

        # add the codes to files
        df = pandas.read_csv(io.StringIO(codes))
        df = df.rename(columns={'file': 'file_id'})
        file_cache = {}

        def fn(e):
            if e not in file_cache:
                file_cache[e] = File.objects.filter_by_identifier(e).first().id_as_str
            return file_cache.get(e)

        df['file_id'] = df['file_id'].apply(fn)

        # get all codes from db as some concept may already have existed in database
        code_cache = {}

        def fn(e):
            k = f'{e.codesystem}#{e.code}'
            if k not in code_cache:
                code_cache[k] = Code.objects.filter(codesystem__uri=e.codesystem, code=e.code).first().id_as_str
            return code_cache[k]

        df['code_id'] = df.apply(fn, axis=1)
        df = df.drop(columns=['origin', 'code', 'codesystem'])
        # add codes to files
        db_utils.insert_with_copy_from_and_tmp_table(df, File.codes.through.objects.model._meta.db_table,
                                                     insert_columns='file_id, code_id')
        # add codes to share
        df = df.drop(columns=['file_id'])
        df['share_id'] = kwargs.get('share').id_as_str
        db_utils.insert_with_copy_from_and_tmp_table(df, Share.codes.through.objects.model._meta.db_table,
                                                     insert_columns='share_id, code_id')

        # add codes to project
        df = df.drop_duplicates()
        df = df.drop(columns=['share_id'])
        project = kwargs.get('project')
        # add to project
        if project is not None:
            if project.codeset is None:
                project.codeset = CodeSet.objects.create()
                project.save(update_fields=['codeset'])
            df['codeset_id'] = project.codeset.id_as_str
            db_utils.insert_with_copy_from_and_tmp_table(df, CodeSet.codes.through.objects.model._meta.db_table,
                                                         insert_columns='code_id, codeset_id')


class CodeSet(Base):
    '''
    A CodeSet represents a set of codes that originate from different code systems. A CodeSet is attached to a project.
    All codes that exist in a project e.g. as labels are included in this CodeSet.
    '''
    codes = models.ManyToManyField(Code, related_name='codesets')
