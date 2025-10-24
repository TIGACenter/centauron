import io
import math
import uuid
from pathlib import Path
from typing import Optional

import pandas
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core import db_utils
from apps.core.models import Base, BaseResource, IdentifieableMixin, CreatedByMixin, \
    OriginMixin
from apps.node.models import Node
from apps.project.project_case.models import Case
from apps.storage.managers import FileManager
from apps.user.user_profile.models import Profile


class File(CreatedByMixin, OriginMixin, IdentifieableMixin, BaseResource):
    class Meta:
        indexes = [models.Index(fields=['identifier'])]

    name = models.CharField(max_length=1000)

    content_type = models.CharField(max_length=100, default=None, null=True, blank=True)
    imported = models.BooleanField(default=False)  # if file is imported or not
    objects = FileManager()
    case = models.ForeignKey("project_case.Case", on_delete=models.CASCADE, null=True, default=None,
                             related_name="files")
    import_folder = models.ForeignKey('storage_importer.ImportFolder', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='files')
    # the file this file originated from e.g. tile -> slide
    originating_from = models.ForeignKey('File', on_delete=models.DO_NOTHING, related_name='children_files', null=True,
                                         blank=True)

    original_filename = models.CharField(max_length=1000)
    original_path = models.CharField(max_length=1000)
    path = models.CharField(max_length=1000, null=True, default=None, blank=True)
    size = models.BigIntegerField(default=-1)

    @property
    def as_path(self) -> Path | None:
        if self.path is None:
            return None
        return settings.STORAGE_DATA_DIR / self.path

    @property
    def origin_via(self) -> Optional['Profile']:
        '''
        Returns the challenge organizer node that can be used to download the file.
        :return: None if file was not imported in the context of a challenge
        '''
        # TODO for now take the first dataset and assume all users got that data from the same node
        # TODO actually one would need to filter here for the challenge that was shared with the current user
        qs_in_dataset_from_other_nodes = self.datasets.exclude(challenge__origin__node__identifier=settings.IDENTIFIER)
        first = qs_in_dataset_from_other_nodes.first()
        if first is not None:
            return first.challenge.origin
        return None

    def __str__(self):
        return self.name

    @staticmethod
    def import_file(**kwargs):
        # TODO check if the metadataimporter can be used here
        files = kwargs.get('files')
        created_by = kwargs.get('created_by')

        if files is None or len(files) == 0:
            return
        df = pandas.read_csv(io.StringIO(files))
        now = timezone.now().isoformat()
        df = df.rename(columns={'origin': 'origin_id', 'case': 'case_id'})
        df['imported'] = False
        profile_cache = {}

        def fn(e):
            if e not in profile_cache:
                try:
                    profile = Profile.objects.get_by_identifier(e)
                except Profile.DoesNotExist:
                    # TODO use Profile.create_user here also at all other places of imports
                    profile = Profile.objects.create_and_return(e)
                profile_cache[e] = profile.id_as_str
            return profile_cache.get(e)

        df['origin_id'] = df['origin_id'].apply(fn)
        if created_by is not None:
            df['created_by_id'] = created_by.id_as_str


        # filter out files that are already existing in database
        identifiers = df['identifier'].to_list()
        qs = File.objects.filter_by_identifiers(identifiers).distinct()
        existing_files = {e[0]: e[1] for e in qs.values_list('identifier', 'id')}
        existing_rows = df['identifier'].isin(existing_files.keys())
        df['existing'] = existing_rows

        def fn_set_id(e):
            if not e['existing']: return str(uuid.uuid4())
            return existing_files[e['identifier']]

        df['id'] = df.apply(fn_set_id, axis=1)  # df.apply(lambda e: str(uuid.uuid4()), axis=1)

        df_id = df[['id']]

        # filter out existing files
        df = df[~existing_rows]
        df = df.drop(columns=['existing'])
        if 'case_id' in df.columns:
            case_cache = {}

            def fn(e):
                if not isinstance(e, str) and math.isnan(e):
                    return None
                if e not in case_cache:
                    # case should exist here as it was already imported
                    case_cache[e] = Case.objects.filter_by_identifier(e).first().id_as_str
                return case_cache.get(e)

            df['case_id'] = df['case_id'].apply(fn)
        df['date_created'] = now
        df['last_modified'] = now
        db_utils.insert_with_copy_from_and_tmp_table(df, File.objects.model._meta.db_table)

        if 'share' in kwargs:
            # add to share
            df_id['share_id'] = kwargs.get('share').id_as_str
            df_id = df_id.rename(columns={'id': 'file_id'})
            from apps.share.models import Share
            db_utils.insert_with_copy_from_and_tmp_table(df_id, Share.files.through.objects.model._meta.db_table,
                                                         insert_columns='file_id, share_id')

        # add to project
        for_user = kwargs.get('for_user')
        project = kwargs.get('project')
        if project is not None and for_user is not None:
            df_id['project_id'] = project.id_as_str
            df_id = df_id.drop(columns=['share_id'])
            df_id = df_id.rename(columns={'id': 'file_id'})
            df_id['user_id'] = for_user.id_as_str
            now = timezone.now().isoformat()
            df_id['date_created'] = now
            df_id['last_modified'] = now
            df_id['imported'] = False

            def fn_set_id(e):
                return str(uuid.uuid4())

            df_id['id'] = df_id.apply(fn_set_id, axis=1)

            # TODO set imported = True if the recipient has download permission and the file is imported on the client

            from apps.project.models import Project
            db_utils.insert_with_copy_from_and_tmp_table(df_id, Project.files.through.objects.model._meta.db_table,
                                                         insert_columns='id, imported, file_id, project_id, user_id, date_created, last_modified')

    def remove_file(self):
        if not self.imported:
            return
        if not self.as_path.exists():
            return

        self.as_path.unlink()
        self.imported = False
        self.path = None
        self.import_folder = None
        self.save(update_fields=['imported', 'path', 'import_folder'])
