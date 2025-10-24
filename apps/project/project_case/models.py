import io
import logging
import uuid

import pandas
from annoying.fields import AutoOneToOneField
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone

from apps.core import db_utils
from apps.core.models import Base, CreatedByMixin, IdentifieableMixin, OriginMixin, BaseResource
from apps.project.project_case.managers import CaseManager
from apps.study_management.models import Study
from apps.terminology.models import Code
from apps.user.user_profile.models import Profile


class Case(CreatedByMixin, OriginMixin, IdentifieableMixin, BaseResource):
    objects = CaseManager()
    name = models.CharField(max_length=200)
    projects = models.ManyToManyField("project.Project", related_name="cases", blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['identifier', 'created_by', 'origin'], name='unique_case_per_user')
        ]

    def __str__(self):
        return self.name

    def code_list_string_rep(self):
        v = self.files.values_list('codes', flat=True)
        return [c.get_readable_str() for c in Code.objects.filter(id__in=v)]

    def contained_in_studies(self):
        study_pks = self.files.values_list('study_arms__study_id', flat=True).distinct()
        return Study.objects.filter(pk__in=study_pks)

    @staticmethod
    def import_case(**kwargs):
        cases = kwargs.get('cases')
        if cases is None:
            logging.info('No cases to import')
            return

        df = pandas.read_csv(io.StringIO(cases))
        now = timezone.now().isoformat()
        # df['created_by_id'] = kwargs.get('created_by').id_as_str
        # # FIXME origin can be different than the sending node.
        # df['origin_id'] = kwargs.get('origin').id_as_str
        df['date_created'] = now
        df['last_modified'] = now

        # filter out files that are already existing in database
        identifiers = df['identifier'].to_list()
        qs = Case.objects.filter_by_identifiers(identifiers).distinct()
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

        profile_cache = {}

        def from_profile_cache(e):
            if e not in profile_cache:
                try:
                    profile = Profile.objects.get_by_identifier(e)
                except Profile.DoesNotExist:
                    profile = Profile.objects.create_and_return(e)
                profile_cache[e] = profile.id_as_str
            return profile_cache.get(e)

        # if len(df.index) > 0:
        df = df.rename(columns={'origin': 'origin_id'})
        df['origin_id'] = df['origin_id'].apply(from_profile_cache)

        db_utils.insert_with_copy_from_and_tmp_table(df, Case.objects.model._meta.db_table)
        # add to share
        df_id['share_id'] = kwargs.get('share').id_as_str
        df_id = df_id.rename(columns={'id': 'case_id'})
        from apps.share.models import Share
        db_utils.insert_with_copy_from_and_tmp_table(df_id, Share.cases.through.objects.model._meta.db_table,
                                                     insert_columns='share_id, case_id')

        project = kwargs.get('project')
        if project is not None:
            # add to project
            df_id['project_id'] = project.id_as_str
            df_id = df_id.drop(columns=['share_id']).rename(columns={'id': 'case_id'})
            from apps.project.models import Project
            db_utils.insert_with_copy_from_and_tmp_table(df_id, Case.projects.through.objects.model._meta.db_table,
                                                         insert_columns='project_id, case_id')


class CaseDescription(Base):
    description = models.TextField(null=False)
    case = AutoOneToOneField(Case, on_delete=models.CASCADE, related_name="description")
    # application = models.ForeignKey(Application, on_delete=models.CASCADE)
