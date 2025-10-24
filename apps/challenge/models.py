import csv
import io
import logging
import uuid
from io import StringIO

import pandas
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.blockchain.messages import CreateMessage, Object, Identifiable
from apps.blockchain.models import Log
from apps.challenge.managers import ChallengeManager
from apps.core.db_utils import insert_with_copy_from_and_tmp_table
from apps.core.models import BaseResource, IdentifieableMixin, CreatedByMixin, OriginMixin
from apps.project.models import Project
from apps.storage.models import File
from apps.user.user_profile.models import Profile


class Challenge(CreatedByMixin, OriginMixin, IdentifieableMixin, BaseResource):
    objects = ChallengeManager()
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, related_name='challenges')
    open_from = models.DateTimeField()
    open_until = models.DateTimeField()  # TODO check in save method if open_from < open_until
    description = models.TextField(null=True, blank=True)
    tags = models.CharField(max_length=200, default=None, null=True, blank=True)
    pipeline = models.OneToOneField('computing.ComputingPipeline', on_delete=models.SET_NULL, null=True, blank=True)
    pipeline_yml = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    @property
    def tags_arr(self):
        return [t.strip() for t in self.tags.split(',')]

    @property
    def data_origins(self):
        return Profile.objects.filter(pk__in=self.pipeline.stages.values_list('data_origins', flat=True).distinct())

    @property
    def has_multiple_data_origins(self):
        return self.data_origins.exclude(node__identifier=settings.IDENTIFIER).count() > 0

    @property
    def i_am_host(self):
        return self.origin.identifier == settings.IDENTIFIER

    def get_absolute_url(self):
        return reverse('challenge:detail', kwargs=dict(pk=self.pk))

    def to_identifiable(self):
        return Identifiable(model="challenge", display=self.name, identifier=self.identifier)

    def send_created_broadcast(self):
        msg = CreateMessage(
            object=Object(model="challenge", value=self.to_identifiable()),
            actor=self.created_by.to_actor(),
            context={"project": self.project.to_identifiable()}
        )
        Log.send_broadcast(msg)

    @staticmethod
    def import_challenge(challenge, share):
        if challenge is None: return

        df = pandas.read_csv(io.StringIO(challenge))
        now = timezone.now().isoformat()
        df['date_created'] = now
        df['last_modified'] = now

        identifiers = df['identifier'].to_list()
        qs = Challenge.objects.filter_by_identifiers(identifiers).distinct()
        existing_files = {e[0]: e[1] for e in qs.values_list('identifier', 'id')}
        existing_rows = df['identifier'].isin(existing_files.keys())
        df['existing'] = existing_rows

        def fn_set_id(e):
            if not e['existing']: return str(uuid.uuid4())
            return existing_files[e['identifier']]

        df['id'] = df.apply(fn_set_id, axis=1)  # df.apply(lambda e: str(uuid.uuid4()), axis=1)
        # filter out existing files
        df_existing_challenges = df[existing_rows]
        df = df[~existing_rows]
        df = df.drop(columns=['existing'])

        # get the origin node id
        origin_cache = {}

        def fn_origin(e):
            if e not in origin_cache:
                origin_cache[e] = Profile.objects.get_by_identifier(e).id_as_str
            return origin_cache[e]

        df['origin'] = df['origin'].apply(fn_origin)

        project_cache = {}

        def fn_project(e):
            if e not in project_cache:
                project_cache[e] = Project.objects.get_by_identifier(e).id_as_str
            return project_cache[e]

        df['project'] = df['project'].apply(fn_project)
        df = df.rename(columns={'project': 'project_id', 'origin': 'origin_id'})
        insert_with_copy_from_and_tmp_table(df, Challenge.objects.model._meta.db_table)

        # add to share
        df_id = df[['id']]
        df_id['share_id'] = share.id_as_str
        df_id = df_id.rename(columns={'id': 'challenge_id'})
        from apps.share.models import Share
        insert_with_copy_from_and_tmp_table(df_id, Share.challenges.through.objects.model._meta.db_table,
                                            insert_columns='share_id, challenge_id')

        # TODO import the computing pipeline? is this even necessary?

        # update existing challenges.
        # iterating a dataframe like this is slow but this will always be only a single challenge so it doesn't matter
        for idx, row in df_existing_challenges.iterrows():
            c = Challenge.objects.get(pk=row['id'])
            c.description = row['description']
            c.name = row['name']
            c.open_from = row['open_from']
            c.open_until = row['open_until']
            c.save()


    @staticmethod
    def import_data_files_for_stages(data_files):
        from apps.computing.models import ComputingJobDefinition

        logging.info('Start import data files.')
        current_node_identifier = settings.IDENTIFIER

        # TODO modify the data files: if the file is from this node, then set the correct path
        for cjd_identifier, file_content in data_files.items():
            cjd = ComputingJobDefinition.objects.filter_by_identifier(cjd_identifier).first()

            data_file = settings.STORAGE_DATA_DIR / str(uuid.uuid4())
            with data_file.open('w') as f:
                reader = csv.DictReader(StringIO(file_content), delimiter=';')
                writer = csv.DictWriter(f, fieldnames=reader.fieldnames, delimiter=';', quoting=csv.QUOTE_ALL)
                writer.writeheader()
                # for files of the current node replace the path or a submission cannot read the file
                for row in reader:
                    if 'identifier' in row and row['origin'] == current_node_identifier:
                        qs = File.objects.filter(identifier=row['identifier'])
                        if qs.exists():
                            row['path'] = qs.first().path
                    writer.writerow(row)

            cjd.data_file = data_file.name
            cjd.save(update_fields=['data_file'])
        logging.info('Data files imported.')
