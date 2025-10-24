import io
import uuid

import pandas
from django.db import models
from django.utils import timezone

from apps.core import db_utils
from apps.core.managers import BaseManager
from apps.core.models import OriginMixin, IdentifieableMixin, BaseResource, CreatedByMixin
from apps.node.models import Node
from apps.project.models import ProjectExtraData
from apps.storage.models import File
from apps.user.user_profile.models import Profile


class ExtraDataManager(BaseManager):
    pass


class ExtraData(CreatedByMixin, OriginMixin, IdentifieableMixin, BaseResource):
    '''
    Used as a container to store other data coming from other applications.
    Data needs to be json.
    '''
    objects = ExtraDataManager()

    class Meta:
        constraints = [models.Index(name='idx_file', fields=['file'])]

    file = models.ForeignKey('storage.File', on_delete=models.CASCADE, related_name='extra_data')
    data = models.JSONField(blank=True, default=dict)
    application_identifier = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True, default=None)

    @staticmethod
    def import_extra_data(**kwargs):
        share = kwargs.get('share', None)
        data = kwargs.get('extra_data', None)
        project = kwargs.get('project', None)
        for_user = kwargs.get('for_user')

        # file,identifier,data,application_identifier,description,created_by,origin
        if data is None:
            return

        df = pandas.read_csv(io.StringIO(data))
        now = timezone.now().isoformat()
        df = df.rename(columns={'origin': 'origin_id',
                                'file': 'file_id',
                                'created_by': 'created_by_id'})
        df['created_by_id'] = for_user.id_as_str
        # replace origins
        origin_cache = {}

        def fn(e):
            if e not in origin_cache:
                origin_cache[e] = Profile.objects.get_by_identifier(e).id_as_str
            return origin_cache[e]

        df['origin_id'] = df['origin_id'].apply(fn)

        # replace file ids
        file_cache = {}

        def fn(e):
            if e not in file_cache:
                file_cache[e] = File.objects.get_by_identifier(e).id_as_str
            return file_cache[e]

        df['file_id'] = df['file_id'].apply(fn)

        # replace created_by ids
        created_by_cache = {}

        def fn(e):
            if e not in created_by_cache:
                try:
                    profile = Profile.objects.get_by_identifier(e)
                except Profile.DoesNotExist:
                    profile = Profile.objects.create_and_return(e)
                created_by_cache[e] = profile.id_as_str
            return created_by_cache[e]

        df['created_by_id'] = df['created_by_id'].apply(fn)
        # filter out existing rows
        identifiers = df['identifier'].to_list()
        qs = ExtraData.objects.filter_by_identifiers(identifiers).distinct()
        existing_files = {e[0]: e[1] for e in qs.values_list('identifier', 'id')}
        existing_rows = df['identifier'].isin(existing_files.keys())

        df['existing'] = existing_rows
        def fn_set_id(e):
            if not e['existing']: return str(uuid.uuid4())
            return existing_files[e['identifier']]

        df['id'] = df.apply(fn_set_id, axis=1)

        df['date_created'] = now
        df['last_modified'] = now
        df_org = df
        df = df_org[~existing_rows]
        df_existing = df_org[existing_rows]
        df = df.drop(columns=['existing'])
        df_existing = df_existing.drop(columns=['existing'])

        dest_tbl_name = ExtraData.objects.model._meta.db_table
        db_utils.insert_with_copy_from_and_tmp_table(df, dest_tbl_name)
        db_utils.update_from_tmp_table(df_existing, dest_tbl_name,
                                       f"data = x.data, description = x.description",
                                       f"{dest_tbl_name}.identifier = x.identifier")

        # add to share
        if 'share' in kwargs:
            df_id = df[['id']]
            df_id['share_id'] = kwargs.get('share').id_as_str
            df_id = df_id.rename(columns={'id': 'extradata_id'})
            from apps.share.models import Share
            db_utils.insert_with_copy_from_and_tmp_table(df_id,
                                                         Share.extra_data.through.objects.model._meta.db_table,
                                                         insert_columns='extradata_id, share_id')
        if project is not None and for_user is not None:
            # file,identifier,data,application_identifier,description,created_by,origin
            df_proj = df[['id']]
            df_proj = df_proj.rename(columns={'id': 'extra_data_id'})
            def fn_set_id(e):
                return str(uuid.uuid4())

            df_proj['id'] = df_proj.apply(fn_set_id, axis=1)
            df_proj['project_id'] = project.id_as_str
            df_proj['imported'] = True
            df_proj['user_id'] = for_user.id_as_str
            now = timezone.now().isoformat()
            df_proj['date_created'] = now
            df_proj['last_modified'] = now
            db_utils.insert_with_copy_from_and_tmp_table(df_proj,
                                                         ProjectExtraData.objects.model._meta.db_table,
                                                         insert_columns='date_created, last_modified, id, imported, extra_data_id, project_id, user_id')
