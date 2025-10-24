import abc
import csv
import io
import logging
from typing import Any, Dict

import pandas
import pandas as pd
from django.conf import settings
from django.db import connection
from django.db.models import QuerySet

from apps.challenge.challenge_dataset.models import Dataset
from apps.challenge.challenge_dataset.serializers import DatasetSerializer
from apps.challenge.challenge_submission.models import Submission
from apps.challenge.challenge_submission.serializers import SubmissionSerializer, EvaluationCodeSerializer
from apps.challenge.challenge_targetmetric.models import TargetMetric
from apps.challenge.challenge_targetmetric.serializers import TargetMetricSerializer
from apps.challenge.models import Challenge
from apps.challenge.serializers import ChallengeSerializer
from apps.computing.computing_artifact.models import ComputingJobArtifact, ComputingJobResult
from apps.computing.computing_artifact.serializers import ComputingJobArtefactSerializer
from apps.computing.computing_executions.models import ComputingJobExecution
from apps.computing.computing_executions.serializers import ComputingJobExecutionSerializer
from apps.computing.computing_log.models import ComputingJobLogEntry
from apps.computing.computing_log.serializers import ComputingJobLogEntrySerializer
from apps.computing.models import ComputingJobDefinition
from apps.computing.serializers import ComputingJobDefinitionSerializer, ComputingPipelineFullSerializer
from apps.core import identifier, db_utils
from apps.core.db_utils import insert_with_copy_from_and_tmp_table
from apps.permission.models import Permission
from apps.project.models import Project
from apps.project.project_case.models import Case
from apps.project.project_case.serializers import CaseSerializer
from apps.share.models import Share
from apps.storage.extra_data.models import ExtraData
from apps.storage.models import File
from apps.storage.serializers import FileSerializer
from apps.terminology.models import CodeSystem, Code
from apps.user.user_profile.models import Profile


def create_share(name: str,
                 *,
                 created_by: Profile,
                 description: str | None = None,
                 datasets: QuerySet[Dataset] | None = None,
                 files: QuerySet[File] | list[File] | None = None,
                 challenges: QuerySet[Challenge] | None = None,
                 logs: QuerySet[ComputingJobLogEntry] | None = None,
                 artefacts: QuerySet[ComputingJobArtifact] | None = None,
                 computing_job_definitions: QuerySet[ComputingJobDefinition] | None = None,
                 computing_job_executions: QuerySet[ComputingJobExecution] | None = None,
                 cases: QuerySet[Case] | list[Case] | None = None,
                 metrics: QuerySet[TargetMetric] | list[TargetMetric] | None = None,
                 ) -> Share:
    share = Share.objects.create(name=name,
                                 created_by=created_by,
                                 description=description,
                                 identifier=identifier.create_random('share'))
    if files is not None:
        share.files.set(files)
        if isinstance(cases, QuerySet):
            files = files.all()
    if challenges is not None:
        share.challenges.set(challenges)
    if cases is not None:
        share.cases.set(cases)
        if isinstance(cases, QuerySet):
            cases = cases.all()
        # for each case that is included in this share, also add all files. TODO this means that only whole cases can be shared.
        # files += [f for c in cases for f in c.files.all()]

    if datasets is not None:
        share.datasets.set(datasets)

    # TODO serialize files, challenges and cases to a "package"
    # package structure looks like this:
    # {
    #     "challenges": [
    #         {
    #             "name": "",
    #             "datasets": [
    #                 {
    #                     "name": "",
    #                     "type": "TRAINING | VALIDATION",
    #                     "identifier": "dataset.identiifer#1"
    #                 }
    #             ]
    #         }
    #     ],
    #     "cases": [
    #         {
    #             "name": "",
    #             "identifier": "case.identifier#1",
    #             "dataset": "dataset.identifier#1"
    #
    #         }
    #     ],
    #     "files": [
    #         {
    #             "name": "",
    #             "identifier": "file.identifier#1",
    #             "permissions": ["transfer","view","annotate"],
    #             "origin": "profile.identifier#1"
    #             "case": "case.identifier#1",
    #             "path": { ... }
    #         }
    #     ],
    # }
    # dynamically set of also project / dataset etc should be serialized for case, file etc. https://www.django-rest-framework.org/api-guide/serializers/#dynamically-modifying-fields
    # for identifiers et al: https://www.django-rest-framework.org/api-guide/relations/#stringrelatedfield
    package = {}
    exclude_fields: list[str] = []
    if cases is None or len(cases) == 0:
        exclude_fields.append('case')
    if datasets is None or len(datasets) == 0:
        exclude_fields.append('datasets')
    if challenges is None or len(challenges) == 0:
        exclude_fields.append('challenges')
        exclude_fields.append('challenge')

    dataset_identifiers = None
    if datasets is not None:
        datasets = datasets.all() if isinstance(datasets, QuerySet) else datasets
        dataset_identifiers = [d.pk for d in datasets]
    # provide dataset ids here to filter out datasets identifier that are not included in this share.
    # TODO if files and cases are too many then serialize to CSV instead of json for efficiency reasons
    if files is not None:
        kwargs_files = dict()
        if datasets is not None:
            kwargs_files['contained_datasets'] = dataset_identifiers
        package['files'] = \
            FileSerializer(files, many=True, exclude_fields=exclude_fields,
                           **kwargs_files).data
    if cases is not None:
        kw = {}
        if dataset_identifiers is not None:
            kw['contained_datasets'] = dataset_identifiers
        package['cases'] = CaseSerializer(cases, many=True, exclude_fields=exclude_fields, **kw).data
    if datasets is not None:
        package['datasets'] = DatasetSerializer(datasets, many=True, exclude_fields=exclude_fields).data
    if challenges is not None:
        package['challenges'] = ChallengeSerializer(challenges, many=True, exclude_fields=exclude_fields).data
    if logs is not None:
        package['logs'] = ComputingJobLogEntrySerializer(logs, many=True).data
        share.computing_job_logs.set(logs)

    if artefacts is not None:
        package['artefacts'] = ComputingJobArtefactSerializer(artefacts, many=True).data
        share.computing_job_artefacts.set(artefacts)

    if computing_job_definitions is not None:
        package['computing_job_definitions'] = ComputingJobDefinitionSerializer(computing_job_definitions,
                                                                                many=True,
                                                                                fields=('identifier', 'submission',
                                                                                        'name', 'batch_size',
                                                                                        'total_batches',)).data
        share.computing_job_definitions.set(computing_job_definitions)

    if computing_job_executions is not None:
        package['computing_job_executions'] = ComputingJobExecutionSerializer(computing_job_executions, many=True).data
        share.computing_job_executions.set(computing_job_executions)

    if metrics is not None:
        package['metrics'] = TargetMetricSerializer(metrics, many=True).data

    share.content = package
    share.save()

    return share


class Handler:

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @abc.abstractmethod
    def handle(self, package, share, data):
        '''
        Should add data to dict `package`.
        :param package:
        :param share:
        :param data:
        :return:
        '''
        pass

    def set(self, share, data):
        '''
        Adds data to the share.
        :param share:
        :param data:
        :return:
        '''
        pass


class FileHandler(Handler):
    __name__ = 'file'

    def handle(self, package, share, data):
        # assume a list of uuids or a queryset
        if isinstance(data, list):
            file_ids = set(data)
        else:
            file_ids = data.values_list('id', flat=True)

        if len(file_ids) == 0:
            return

        ids = ','.join(list(map(lambda e: f'\'{e}\'', file_ids)))
        with connection.cursor() as cursor, io.StringIO() as buffer:
            sql_1 = f'''select
                            upp.identifier as origin,
                            pcc.identifier as
                            case,
                            sf.identifier,
                            sf.name,
                            sf.content_type,
                            sf.size,
                            sf.original_filename,
                            sf.original_path
                        from
                            {File.objects.model._meta.db_table} sf
                        left join {Case.objects.model._meta.db_table} pcc on
                            sf.case_id = pcc.id
                        left join {Profile.objects.model._meta.db_table} upp on
                            sf.origin_id = upp.id
                        where sf.id in ({ids})'''
            sql = f'copy ({sql_1}) to stdout with csv header'
            cursor.copy_expert(sql, buffer)
            buffer.seek(0)
            csv = buffer.read()
            package['files'] = csv

    def set(self, share, data):
        assert share is not None
        logging.debug('Adding files to share.')
        ids = data.values_list('id', flat=True)
        with io.StringIO() as buffer:
            writer = csv.writer(buffer)
            header = ['share_id', 'file_id']
            writer.writerow(header)
            writer.writerows([[share.id_as_str, str(i)] for i in ids])

            buffer.seek(0)
            df = pandas.read_csv(buffer)
            db_utils.insert_with_copy_from_and_tmp_table(df, Share.files.through.objects.model._meta.db_table,
                                                         ','.join(header))

            # tmp_tbl_name = ''.join(random.choice(string.ascii_uppercase) for _ in range(5))
            # cursor.execute(f'create temp table {tmp_tbl_name} as {sql} limit 1')
            # cursor.execute(f'truncate table {tmp_tbl_name}')
            #
            # cursor.copy_expert(
            #     f'copy {Share.files.through.objects.model._meta.db_table}({",".join(header)}) from stdin csv header',
            #     buffer)
        logging.debug('Done adding files to share.')
    # TODO add csv now to package. the question remains how to actually sort those files by dataset or case or whatever.
    # TODO maybe this can be done via some sql generator


class PermissionHandler(Handler):
    __name__ = 'permissions'

    def handle(self, package, share, data):
        if isinstance(data, QuerySet):
            data = list(data)

        if len(data) == 0:
            return

        # data already in the required format
        if not isinstance(data, str):
            # TODO sql injection possible here
            data = ','.join(list(map(lambda e: f'\'{e}\'', data)))

        sql = f'''
                select
                    object_identifier,
                    permission,
                    action
--                     string_agg(action, ',') as permission
                from
                    {Permission.objects.model._meta.db_table}
                where
                    object_identifier in ({data})
        '''

        with connection.cursor() as cursor, io.StringIO() as buffer:
            cursor.copy_expert(f'copy ({sql}) to stdout with csv header', buffer)
            buffer.seek(0)
            csv = buffer.read()
            package['permissions'] = csv
            # permissions are not stored as part of the share. they are just part of the shared "package" --> no share.permissions exists.


class SubmissionHandler(Handler):
    __name__ = 'submission'

    def handle(self, package, share, data):
        package['submission'] = SubmissionSerializer(data['submission']).data
        data_files = data.get('data_files')
        if data_files is not None:
            package['data_files'] = {}
            for stage_identifier, data_file_name in data_files.items():
                with (settings.STORAGE_DATA_DIR / data_file_name).open('r') as f:
                    package['data_files'][stage_identifier] = f.read()

    def set(self, share, data):
        share.submissions.add(data['submission'])


class TilesetHandler(Handler):
    __name__ = 'tileset'

    def handle(self, package, share, data):
        pass


class CodeSystemHandler(Handler):
    __name__ = 'codesystem'

    def handle(self, package, share, data):
        '''

        :param package:
        :param share:
        :param data: A QuerySet containing all the CodeSystems that should be shared.
        :return:
        '''
        vals = data.values_list('id', flat=True).distinct()
        if len(vals) == 0:
            return

        ids = ','.join(list(map(lambda e: f'\'{e}\'', vals)))
        sql = f'''
            select cs.name, cs.uri, o.identifier as origin from {CodeSystem.objects.model._meta.db_table} cs
            left join {Profile.objects.model._meta.db_table} o on o.id = cs.origin_id
            where cs.id in ({ids})
            '''

        with connection.cursor() as cursor, io.StringIO() as buffer:
            cursor.copy_expert(f'copy ({sql} )to stdout with csv header', buffer)
            buffer.seek(0)
            package['codesystems'] = buffer.read()

    def set(self, share, data):
        assert share is not None
        logging.debug('Adding codesystems to share.')
        with connection.cursor() as cursor, io.StringIO() as buffer:
            writer = csv.writer(buffer)
            header = ['share_id', 'codesystem_id']
            # remove duplicated codes
            unique_data = {(share.id, i.id_as_str) for i in data}
            writer.writerow(header)
            writer.writerows([[i[0], i[1]] for i in unique_data])
            # no need for escaping sql params. this is only inserting ids.
            buffer.seek(0)
            cursor.copy_expert(
                f'copy {Share.codesystem.through.objects.model._meta.db_table}({",".join(header)}) from stdin csv header',
                buffer)
        logging.debug('Done adding codesystems to share.')


class CodesHandler(Handler):
    __name__ = 'codes'
    name_files = 'codes-file'
    name_cases = 'codes'

    def handle(self, package, share, data):
        '''

        :param package:
        :param share:
        :param data: a list of named tuples (id, codes) with id being the file id and codes being the code id.
        :return:
        '''
        table_model = File if self.__name__ == self.name_files else Case
        table = table_model.codes.through.objects.model._meta.db_table if self.__name__ == self.name_files else ''
        # TODO depending on case or file or whatever, join different table here, also adapt where condition
        # TODO data is in format: (id, concepts). turn into separate lists and add to query here.
        # TODO check if both f.id in and c.id in are actually correct and select no more data than necessary
        # if isinstance(data, list):
        #     ids = [[r]]
        ids = [[r.id, r.codes] for r in data if r.codes is not None]
        if len(ids) == 0:
            return
        # TODO copy to temp table first
        f_ids = ','.join([f'\'{r[0]}\'' for r in ids])
        c_ids = {r[1] for r in ids}  # unique ids for codes
        c_ids = ','.join([f'\'{r}\'' for r in c_ids])
        # FIXME this query is not working
        sql = f'''
                    select f.identifier as file, u.identifier as origin, c.code as code, cs.uri as codesystem from {table} sfc
                    join {File.objects.model._meta.db_table} f on sfc.file_id = f.id
                    join {Code.objects.model._meta.db_table} c on sfc.code_id = c.id
                    left join {Profile.objects.model._meta.db_table} u on c.origin_id = u.id
                    join {CodeSystem.objects.model._meta.db_table} cs on c.codesystem_id = cs.id
                    where f.id in ({f_ids}) and c.id in ({c_ids})
                '''
        #
        #
        # sql = f'select * from {table}'
        #
        #                 ,    join terminology_codesystem cs on c.codesystem_id = cs.id

        with connection.cursor() as cursor, io.StringIO() as buffer:
            cursor.copy_expert(f'copy ({sql}) to stdout with csv header', buffer)
            buffer.seek(0)
            csv = buffer.read()
            package['codes'] = csv

    def set(self, share, data):
        # data is a list/queryset of named tuples (id, codes) with id being the file_id and codes being the code_id
        assert share is not None
        logging.debug('Adding codes to share.')
        with connection.cursor() as cursor, io.StringIO() as buffer:
            writer = csv.writer(buffer)
            header = ['share_id', 'code_id']
            # remove duplicated codes
            unique_data = {(share.id, i.codes) for i in data if i.codes is not None}
            writer.writerow(header)
            writer.writerows([[i[0], i[1]] for i in unique_data])
            # no need for escaping sql params. this is only inserting ids.
            buffer.seek(0)
            cursor.copy_expert(
                f'copy {Share.codes.through.objects.model._meta.db_table}({",".join(header)}) from stdin csv header',
                buffer)
        logging.debug('Done adding codes to share.')


class CaseHandler(Handler):
    __name__ = 'case'

    def handle(self, package, share, data):
        if isinstance(data, list):
            data = set(data)
        else:
            # else assume the data is already a list of uuids
            data = data.values_list('id', flat=True).distinct()
        if len(data) == 0:
            return
        ids = ','.join(list(map(lambda e: f'\'{e}\'', data)))
        sql = f'''
            select c.name, c.identifier, n.identifier as origin from {Case.objects.model._meta.db_table} c
            join {Profile.objects.model._meta.db_table} n on n.id = c.origin_id
            where c.id in ({ids})
        '''

        with connection.cursor() as cursor, io.StringIO() as buffer:
            cursor.copy_expert(f'copy ({sql}) to stdout with csv header', buffer)
            buffer.seek(0)
            package['cases'] = buffer.read()

    def set(self, share, data):
        assert share is not None
        logging.debug('Adding cases to share.')
        with connection.cursor() as cursor, io.StringIO() as buffer:
            writer = csv.writer(buffer)
            header = ['share_id', 'case_id']
            writer.writerow(header)
            writer.writerows([[share.id_as_str, i.id] for i in data])
            # no need for escaping sql params. this is only inserting ids.
            buffer.seek(0)
            cursor.copy_expert(
                f'copy {Share.cases.through.objects.model._meta.db_table}({",".join(header)}) from stdin csv header',
                buffer)
        logging.debug('Done adding codes to share.')


class EvaluationCodeHandler(Handler):
    __name__ = 'evaluation-code'

    def handle(self, package, share, data):
        # not so many items here so use serializer
        package['evaluation-code'] = EvaluationCodeSerializer(data, many=True).data

    def set(self, share, data):
        assert share is not None
        logging.debug('Adding evaluation code to share.')
        share.evaluation_code.set(data)
        logging.debug('Done adding evaluation code to share.')


class ChallengeHandler(Handler):
    __name__ = 'challenge'

    def __init__(self, **kwargs):
        self.computing_pipeline = kwargs.pop('computing_pipeline', 'not-full')
        super().__init__(**kwargs)

    def handle(self, package, share, data, **kwargs):
        '''
        :param package:
        :param share:
        :param data: dict with {'challenge': None, 'datasets': [id], 'target_metrics': [id]}
        :return:
        '''
        challenge = data.get('challenge')
        if challenge is None:
            return

        def query(sql, key):
            with connection.cursor() as cursor, io.StringIO() as buffer:
                cursor.copy_expert(f'copy ({sql}) to stdout with csv header', buffer)
                buffer.seek(0)
                package[key] = buffer.read()

        sql = f'''
                    select c.identifier, c.name, c.open_from, c.open_until, c.description, p.identifier as project, n.identifier as origin
                     from {Challenge.objects.model._meta.db_table} c
                     left join {Profile.objects.model._meta.db_table} n on n.id = c.origin_id
                     left join {Project.objects.model._meta.db_table} p on p.id = c.project_id
                     where c.identifier = '{challenge.identifier}'
                '''
        query(sql, 'challenge')

        datasets = data.get('datasets', [])
        if len(datasets) > 0:
            ids = ','.join(list(map(lambda e: f'\'{e}\'', datasets)))
            sql = f'''
                    select d.identifier, d.name, d.type, d.description, c.identifier as challenge from {Dataset.objects.model._meta.db_table} d
                    left join {Challenge.objects.model._meta.db_table} c on c.id = d.challenge_id
                    where d.id in ({ids})
            '''
            query(sql, 'datasets')

            sql = f'''
                    select d.identifier as dataset, f.identifier as file from {Dataset.files.through.objects.model._meta.db_table} df
                    left join {Dataset.objects.model._meta.db_table} d on d.id = df.dataset_id
                    left join {File.objects.model._meta.db_table} f on f.id = df.file_id
                    where df.dataset_id in ({ids})
                    '''
            query(sql, 'datasets_files')

            sql = f'''
                    select d.identifier as dataset, c.identifier as case from {Dataset.cases.through.objects.model._meta.db_table} dc
                    left join {Dataset.objects.model._meta.db_table} d on d.id = dc.dataset_id
                    left join {Case.objects.model._meta.db_table} c on c.id = dc.case_id
                    where dc.dataset_id in ({ids})
                            '''
            query(sql, 'datasets_cases')

        target_metrics = data.get('target_metrics', [])
        if len(target_metrics) > 0:
            ids = ','.join(list(map(lambda e: f'\'{e}\'', target_metrics)))
            sql = f'''
                    select d.identifier, d.sort, d.key, d.dtype, d.filename, c.identifier as challenge from {TargetMetric.objects.model._meta.db_table} d
                    left join {Challenge.objects.model._meta.db_table} c on c.id = d.challenge_id
                    where d.id in ({ids})
            '''
            query(sql, 'target_metrics')

        # serializer computingpipeline that is connected with
        # however, the pipeline is not that huge so serialize it as json
        if self.computing_pipeline == 'full':
            computing_pipeline_serializer = ComputingPipelineFullSerializer  # challenge.pipeline_yml
            # key = 'yaml'
            # TODO add key entrypoint here
        else:
            # key = 'full'
            computing_pipeline_serializer = ComputingPipelineFullSerializer  # ComputingPipelineSerializer

        package['challenge_pipeline'] = computing_pipeline_serializer(challenge.pipeline).data

    def set(self, share, data):

        def set(buffer, header, table):
            buffer.seek(0)
            insert_with_copy_from_and_tmp_table(pd.read_csv(buffer), table, insert_columns=', '.join(header))

        with io.StringIO() as buffer:
            writer = csv.writer(buffer)
            header = ['share_id', 'challenge_id']
            writer.writerow(header)
            writer.writerows([[share.id_as_str, data['challenge'].id_as_str]])
            # no need for escaping sql params. this is only inserting ids.
            set(buffer, header, Share.challenges.through.objects.model._meta.db_table)

        if 'datasets' in data:
            with io.StringIO() as buffer:
                writer = csv.writer(buffer)
                header = ['share_id', 'dataset_id']
                writer.writerow(header)
                writer.writerows([[share.id_as_str, str(i)] for i in data['datasets']])
                set(buffer, header, Share.datasets.through.objects.model._meta.db_table)

        # TODO also set target metric


class ComputingJobDefinitionHandler(Handler):
    __name__ = 'computing-job-definition'

    def __init__(self, **kwargs):
        self.fields = kwargs.pop('fields', None)
        super().__init__(**kwargs)

    def handle(self, package, share, data):
        ids = ','.join(list(map(lambda e: f'\'{e.id_as_str}\'', data)))
        default_fields = {'cjd.identifier', 'cjd.name', 'cjd.batch_size', 'cjd.total_batches',
                          's.identifier as submission', 'cjd.execution_type'}
        if self.fields is not None:
            fields = self.fields | default_fields
        else:
            fields = default_fields

        fields = ','.join(f for f in fields)
        sql = f'select {fields} from {ComputingJobDefinition.objects.model._meta.db_table} cjd ' \
              f'left join {Submission.objects.model._meta.db_table} s on s.computing_pipeline_id = cjd.pipeline_id ' \
              f'where cjd.id in ({ids})'

        with connection.cursor() as cursor, io.StringIO() as buffer:
            cursor.copy_expert(f'copy ({sql}) to stdout with csv header', buffer)
            buffer.seek(0)
            package['computing_job_definitions'] = buffer.read()

    def set(self, share, data):
        assert share is not None
        logging.debug('Adding computing job definitions to share.')
        with connection.cursor() as cursor, io.StringIO() as buffer:
            writer = csv.writer(buffer)
            header = ['share_id', 'computingjobdefinition_id']
            writer.writerow(header)
            writer.writerows([[share.id_as_str, i.id] for i in data])
            # no need for escaping sql params. this is only inserting ids.
            buffer.seek(0)
            cursor.copy_expert(
                f'copy {Share.computing_job_definitions.through.objects.model._meta.db_table}({",".join(header)}) from stdin csv header',
                buffer)
        logging.debug('Done adding computing job definitions to share.')


class ComputingJobExecutionHandler(Handler):
    __name__ = 'computing-job-execution'

    def handle(self, package, share, data):
        ids = ','.join(list(map(lambda e: f'\'{e.id_as_str}\'', data)))
        sql = f'select cje.identifier, cje.status, cje.started_at, cje.finished_at, cje.batch_number, cjd.identifier as definition from {ComputingJobExecution.objects.model._meta.db_table} cje ' \
              f'left join {ComputingJobDefinition.objects.model._meta.db_table} cjd on cjd.id = cje.definition_id ' \
              f'where cje.id in ({ids})'

        with connection.cursor() as cursor, io.StringIO() as buffer:
            cursor.copy_expert(f'copy ({sql}) to stdout with csv header', buffer)
            buffer.seek(0)
            package['computing_job_executions'] = buffer.read()

    def set(self, share, data):
        assert share is not None
        logging.debug('Adding computing job executions to share.')
        with connection.cursor() as cursor, io.StringIO() as buffer:
            writer = csv.writer(buffer)
            header = ['share_id', 'computingjobexecution_id']
            writer.writerow(header)
            writer.writerows([[share.id_as_str, i.id] for i in data])
            # no need for escaping sql params. this is only inserting ids.
            buffer.seek(0)
            cursor.copy_expert(
                f'copy {Share.computing_job_executions.through.objects.model._meta.db_table}({",".join(header)}) from stdin csv header',
                buffer)
        logging.debug('Done adding computing job executions to share.')


class ComputingJobLogHandler(Handler):
    __name__ = 'computing-job-log'

    def handle(self, package, share, data):
        ids = ','.join(list(map(lambda e: f'\'{e.id_as_str}\'', data)))
        if len(ids) == 0:
            package['logs'] = ''
            return

        sql = f'select cjl.type, cjl.content, cjl.position, cjl.logged_at, cjl.identifier as identifier, cje.identifier as computing_job from {ComputingJobLogEntry.objects.model._meta.db_table} cjl ' \
              f'left join {ComputingJobExecution.objects.model._meta.db_table} cje on cje.id = cjl.computing_job_id ' \
              f'where cjl.id in ({ids})'

        with connection.cursor() as cursor, io.StringIO() as buffer:
            cursor.copy_expert(f'copy ({sql}) to stdout with csv header', buffer)
            buffer.seek(0)
            package['logs'] = buffer.read()

    def set(self, share, data):
        assert share is not None
        logging.debug('Adding computing job log entries to share.')
        with connection.cursor() as cursor, io.StringIO() as buffer:
            writer = csv.writer(buffer)
            header = ['share_id', 'computingjoblogentry_id']
            writer.writerow(header)
            writer.writerows([[share.id_as_str, i.id] for i in data])
            # no need for escaping sql params. this is only inserting ids.
            buffer.seek(0)
            cursor.copy_expert(
                f'copy {Share.computing_job_logs.through.objects.model._meta.db_table}({",".join(header)}) from stdin csv header',
                buffer)
        logging.debug('Done adding computing job log entries to share.')


class ComputingJobArtifactHandler(Handler):
    __name__ = 'computing-job-artifact'

    def handle(self, package, share, data):
        if len(data) == 0:
            return

        ids = ','.join(list(map(lambda e: f'\'{e.id_as_str}\'', data)))
        sql = f'select cjr.identifier as identifier, cjr.date_created, f.identifier as file, cje.identifier as computing_job from {ComputingJobArtifact.objects.model._meta.db_table} cja ' \
              f'left join {ComputingJobExecution.objects.model._meta.db_table} cje on cje.id = cja.computing_job_id ' \
              f'left join {ComputingJobResult.objects.model._meta.db_table} cjr on cjr.id = cja.computingjobresult_ptr_id ' \
              f'left join {File.objects.model._meta.db_table} f on f.id = cja.file_id ' \
              f'where cjr.id in ({ids})'

        with connection.cursor() as cursor, io.StringIO() as buffer:
            cursor.copy_expert(f'copy ({sql}) to stdout with csv header', buffer)
            buffer.seek(0)
            package['artefacts'] = buffer.read()

    def set(self, share, data):
        assert share is not None
        logging.debug('Adding computing job artefacts to share.')
        with connection.cursor() as cursor, io.StringIO() as buffer:
            writer = csv.writer(buffer)
            header = ['share_id', 'computingjobartifact_id']
            writer.writerow(header)
            writer.writerows([[share.id_as_str, i.id] for i in data])
            # no need for escaping sql params. this is only inserting ids.
            buffer.seek(0)
            cursor.copy_expert(
                f'copy {Share.computing_job_artefacts.through.objects.model._meta.db_table}({",".join(header)}) from stdin csv header',
                buffer)
        logging.debug('Done adding computing artefacts entries to share.')


class TypeHandler(Handler):
    __name__ = 'type'

    def handle(self, package, share, data):
        package['type'] = data


class PreviousIdentifierHandler(Handler):
    __name__ = 'previous-identifier'

    def handle(self, package, share, data):
        package['previous-identifier'] = data


class ExtraDataHandler(Handler):
    __name__ = 'extra-data'

    def handle(self, package, share, data):
        extra_data = data  # data.get('extra-data')
        if extra_data is None:
            return

        if isinstance(extra_data, QuerySet) and extra_data.count() == 0:
            return

        ids = ','.join(list(map(lambda e: f'\'{e.id}\'', extra_data)))
        sql = f'''
            select f.identifier as file, c.identifier, c.data, c.application_identifier,
            c.description, p.identifier as created_by, n.identifier as origin
             from {ExtraData.objects.model._meta.db_table} c
             left join {Profile.objects.model._meta.db_table} n on n.id = c.origin_id
             left join {File.objects.model._meta.db_table} f on f.id = c.file_id
             left join {Profile.objects.model._meta.db_table} p on p.id = c.created_by_id
             where c.id in ({ids})
             '''

        with connection.cursor() as cursor, io.StringIO() as buffer:
            cursor.copy_expert(f'copy ({sql}) to stdout with csv header', buffer)
            buffer.seek(0)
            package['extra-data'] = buffer.read()

    def set(self, share, data):
        with io.StringIO() as buffer:
            writer = csv.writer(buffer)
            header = ['share_id', 'extradata_id']
            writer.writerow(header)
            writer.writerows([[share.id_as_str, i.id] for i in data])
            # no need for escaping sql params. this is only inserting ids.
            buffer.seek(0)
            insert_with_copy_from_and_tmp_table(pd.read_csv(buffer),
                                                Share.extra_data.through.objects.model._meta.db_table,
                                                insert_columns=', '.join(header))


class ShareBuilder:

    def __init__(self, pk, name: str, created_by: Profile,
                 origin: Profile = None,
                 description: str = None, file_query: Dict[str, Any] = None,
                 project=None,
                 type=None,
                 challenge=None):
        self.pk = pk
        self.name = name
        self.type = type
        self.created_by = created_by
        self.description = description
        self.handlers = []
        self.handlers_data = {}
        self.origin = origin
        if file_query is None:
            file_query = {}
        self.file_query = file_query
        self.project = project
        self.challenge = challenge
        self.ground_truth = None
        self.identifier = None

    def add_handler(self, *, handler, data, handler_init_kwargs=None):
        if handler_init_kwargs is None:
            handler_init_kwargs = {}
        h = handler(**handler_init_kwargs)
        self.handlers_data[h.__name__] = data
        self.handlers.append(h)
        return self

    def add_type_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=TypeHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_previous_identifier_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=PreviousIdentifierHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_file_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=FileHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_submission_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=SubmissionHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_codesystem_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=CodeSystemHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_permission_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=PermissionHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_case_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=CaseHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_codes_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=CodesHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_challenge_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=ChallengeHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_extra_data_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=ExtraDataHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_computing_job_definition_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=ComputingJobDefinitionHandler, handler_init_kwargs=handler_init_kwargs,
                                data=data)

    def add_computing_job_execution_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=ComputingJobExecutionHandler, handler_init_kwargs=handler_init_kwargs,
                                data=data)

    def add_computing_job_log_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=ComputingJobLogHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_computing_job_artefact_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=ComputingJobArtifactHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def add_evaluation_code_handler(self, data, handler_init_kwargs: Dict[str, Any] = None):
        return self.add_handler(handler=EvaluationCodeHandler, handler_init_kwargs=handler_init_kwargs, data=data)

    def set_ground_truth(self, gt):
        self.ground_truth = gt
        return self

    def build(self, project_identifier=None):
        logging.info('[start] building share')
        if self.identifier is None:
            self.identifier = identifier.create_random('share')
        if self.pk is None:
            kw = dict()
            if self.ground_truth is not None:
                kw['ground_truth'] = self.ground_truth
                kw['ground_truth_schema'] = self.ground_truth.schema

            self.share = Share.objects.create(name=self.name,
                                              description=self.description,
                                              created_by=self.created_by,
                                              file_query=self.file_query,
                                              project=self.project,
                                              origin=self.origin,
                                              identifier=self.identifier,
                                              **kw)
        else:
            self.share = Share.objects.get(pk=self.pk)
            self.share.identifier = self.identifier
            if self.ground_truth is not None:
                self.share.ground_truth = self.ground_truth
                self.share.ground_truth_schema = self.ground_truth.schema
            self.share.save()

        if self.challenge is not None:
            self.share.challenges.add(self.challenge)

        package = {'identifier': str(self.share.identifier)}
        if self.type is not None:
            package['type'] = self.type
        if project_identifier is not None:
            package['project'] = project_identifier
        if self.ground_truth is not None:
            package['ground_truth_schema'] = self.ground_truth.schema.identifier
            package['ground_truth'] = self.ground_truth.identifier

        for handler in self.handlers:
            logging.info('[start] Handler %s', handler.__name__)
            handler.handle(package, self.share, self.handlers_data.get(handler.__name__))
            handler.set(self.share, self.handlers_data.get(handler.__name__))
            logging.info('[end] Handler %s', handler.__name__)

        logging.debug('Handlers finished.')
        self.share.content = package
        self.share.save(update_fields=['content'])

        logging.info('[end] building share')
        return self.share
