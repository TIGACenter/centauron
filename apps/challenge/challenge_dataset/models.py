import csv
import io
import logging
import uuid
from pathlib import Path

import pandas
from django.db import models
from django.db.models import QuerySet
from django.urls import reverse
from django.utils import timezone

from apps.blockchain.messages import CreateMessage, Identifiable, Object
from apps.blockchain.models import Log
from apps.challenge.challenge_dataset.managers import DatasetManager, EvaluationCodeManager
from apps.core.db_utils import insert_with_copy_from_and_tmp_table
from apps.core.models import CreatedByMixin, Base, IdentifieableMixin, OriginMixin
from apps.project.project_case.models import Case
from apps.storage.models import File


class Dataset(CreatedByMixin, OriginMixin, IdentifieableMixin, Base):
    objects = DatasetManager()

    class Type(models.TextChoices):
        TRAINING = "training"
        VALIDATION = "validation"

    name = models.CharField(max_length=500)
    type = models.CharField(max_length=20, default=Type.TRAINING, choices=Type.choices)
    files = models.ManyToManyField(File, related_name="datasets", blank=True)
    cases = models.ManyToManyField("project_case.Case", related_name="datasets", blank=True)
    is_public = models.BooleanField(default=False)
    challenge = models.ForeignKey("challenge.Challenge", on_delete=models.CASCADE, related_name="datasets")
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('challenge:challenge_dataset:detail', kwargs=dict(pk=self.challenge_id, dataset_pk=self.id))

    # TODO obsolete
    def import_(self, model, filter):
        model_is_case = model.lower() == 'case'
        model = Case if model_is_case else File
        filter.pop('projects__id')  # pop this filter for security reason
        qs = model.objects.filter(projects__id=self.challenge.project_id, **filter)
        if model_is_case:
            self.cases.add(*qs.all())
        else:
            self.files.add(*qs.all())

    def write_files_to_csv(self, output: Path):
        # the file is a csv file with two cols: original_filename;path
        with output.open('w') as f:
            writer = csv.DictWriter(f, fieldnames=['original_filename', 'path', 'terms', 'origin', 'identifier'], delimiter=';', quoting=csv.QUOTE_ALL)
            writer.writeheader()
            qs = self.files.all() # we have to use all files here as the data file is also sent to all data providers. not all files are imported here. filter(imported=True, origin=self.origin)
            for c in self.cases.all():
                qs = qs.union(
                    c.files.exclude(pk__in=qs.values_list('pk', flat=True))) #filter(imported=True, origin=self.origin)
            for file in qs:
                # TODO all changes must also be reflected in Challenge.import_data_files_for_stages
                writer.writerow(dict(original_filename=file.original_filename,
                                     origin=file.origin.node.identifier,
                                     path=file.path,
                                     identifier=file.identifier, # identifier necessary for part submission that are run on another node. then the path of the file needs to be fetched from database.
                                     terms=';'.join(file.code_list_identifier_rep())))

    def to_identifiable(self):
        return Identifiable(model="dataset", display=self.name, identifier=self.identifier)

    def broadcast_create_event(self):
        msg = CreateMessage(actor=self.created_by.to_actor(),
                            object=Object(model="dataset", value=self.to_identifiable()),
                            context={"challenge": self.challenge.to_identifiable()})
        Log.send_broadcast(msg)

    @staticmethod
    def import_datasets(share, datasets, datasets_files, datasets_cases):
        if datasets is None: return

        from apps.challenge.models import Challenge
        df = pandas.read_csv(io.StringIO(datasets))
        if len(df.index) == 0:
            logging.info('No datasets found.')
            return
        now = timezone.now().isoformat()
        df['date_created'] = now
        df['last_modified'] = now
        df['is_public'] = True  # by definition a shared dataset is public

        # filter out duplicates
        identifiers = df['identifier'].to_list()
        qs = Dataset.objects.filter_by_identifiers(identifiers).distinct()
        existing_files = {e[0]: e[1] for e in qs.values_list('identifier', 'id')}
        existing_rows = df['identifier'].isin(existing_files.keys())
        df['existing'] = existing_rows

        def fn_set_id(e):
            if not e['existing']: return str(uuid.uuid4())
            return existing_files[e['identifier']]

        df['id'] = df.apply(fn_set_id, axis=1)  # df.apply(lambda e: str(uuid.uuid4()), axis=1)
        # filter out existing files
        df_existing = df[existing_rows]
        df = df[~existing_rows]
        df = df.drop(columns=['existing'])

        # get the origin node id
        challenge_cache = {}

        def fn_challenge(e):
            if e not in challenge_cache:
                challenge_cache[e] = Challenge.objects.get_by_identifier(e).id_as_str
            return challenge_cache[e]

        df['challenge'] = df['challenge'].apply(fn_challenge)
        df = df.rename(columns={'challenge': 'challenge_id'})
        insert_with_copy_from_and_tmp_table(df, Dataset.objects.model._meta.db_table)

        # add to share
        df_id = df[['id']]
        df_id['share_id'] = share.id_as_str
        df_id = df_id.rename(columns={'id': 'dataset_id'})
        from apps.share.models import Share
        insert_with_copy_from_and_tmp_table(df_id, Share.datasets.through.objects.model._meta.db_table,
                                            insert_columns='share_id, dataset_id')

        dataset_cache = {}

        def fn_dataset(e):
            d = e['dataset_id']
            if d not in dataset_cache:
                d = Dataset.objects.filter_by_identifier(d).first()
                if d is not None:  # TODO what to do if dataset not found?
                    dataset_cache[d] = d.id_as_str
            return dataset_cache[d]

        if datasets_files is not None:
            # add files to dataset
            df = pandas.read_csv(io.StringIO(datasets_files))
            if len(df.index) > 0:
                df = df.rename(columns={'dataset': 'dataset_id', 'file': 'file_id'})
                df['dataset_id'] = df.apply(fn_dataset, axis=1)

                def fn_file(e):
                    return File.objects.get_by_identifier(e['file_id']).id_as_str

                df['file_id'] = df.apply(fn_file, axis=1)
                insert_with_copy_from_and_tmp_table(df, Dataset.files.through.objects.model._meta.db_table,
                                                    insert_columns='dataset_id, file_id')

        if datasets_cases is not None:
            # add files to dataset
            df = pandas.read_csv(io.StringIO(datasets_cases))
            if len(df.index) == 0:
                logging.info('No cases for datasets provided.')
            else:
                df = df.rename(columns={'dataset': 'dataset_id', 'case': 'case_id'})
                df['dataset_id'] = df.apply(fn_dataset, axis=1)

                def fn_case(e):
                    return Case.objects.get_by_identifier(e['case_id']).id_as_str

                df['case_id'] = df.apply(fn_case, axis=1)
                insert_with_copy_from_and_tmp_table(df, Dataset.cases.through.objects.model._meta.db_table,
                                                    insert_columns='dataset_id, case_id')
        logging.info(f'Updating {len(df_existing)} datasets.')
        print(df_existing)
        # update fields for existing datasets
        for idx, row in df_existing.iterrows():
            ds = Dataset.objects.get(pk=row['id'])
            ds.name = row['name']
            ds.type = row['type']
            ds.description = row['description']
            ds.save()


    def remove_files(self, files_qs:QuerySet['File']):
        for f in files_qs:
            self.files.remove(f)

class EvaluationCode(CreatedByMixin, IdentifieableMixin, Base):
    objects = EvaluationCodeManager()

    name = models.CharField(max_length=200)
    pyscript = models.TextField(blank=True, default='')
    entrypoint = models.CharField(max_length=100, blank=True)
    schema = models.ForeignKey('project_ground_truth.GroundTruthSchema', on_delete=models.SET_NULL, null=True)
    challenge = models.ForeignKey('challenge.Challenge', on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    @staticmethod
    def import_evaluation_code(share, data):
        from apps.project.project_ground_truth.models import GroundTruthSchema
        if data is None:
            logging.error('No evaluation codes found.')
            return

        from apps.challenge.challenge_submission.serializers import EvaluationCodeSerializer
        serializer = EvaluationCodeSerializer(data=data, many=True)
        # TODO if EVC exists with this identifier, then only update the model.
        serializer.is_valid(raise_exception=True)
        s = []
        for e in serializer.validated_data:
            qs = EvaluationCode.objects.filter(identifier=e['identifier'])
            if qs.exists():
                evc = qs.first()
                evc.entrypoint = e['entrypoint']
                evc.pyscript = e['pyscript']
                evc.schema = e['schema']
                evc.save()
                s.append(evc)
            else:
                s.append(EvaluationCode(**e).save())
        return s
