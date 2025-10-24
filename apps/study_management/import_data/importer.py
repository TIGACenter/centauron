import abc
import csv
import io
import logging
import uuid
from pathlib import Path
from typing import Dict

import pandas as pd
from django.db import connection
from django.db.models import QuerySet
from django.utils import timezone

from apps.core import identifier
from apps.core.models import Annotation
from apps.project.project_case.models import Case
from apps.storage.fileset.models import FileSet
from apps.storage.models import File
from apps.study_management.models import Study
from apps.study_management.tile_management.models import TileSet
from apps.terminology.models import Code, CodeSystem
from apps.user.user_profile.models import Profile
from apps.utils import get_user_node


class AbstractImportHandler(abc.ABC):
    @abc.abstractmethod
    def handle(self, df):
        pass

    def handle_concept(self, df):
        pass


class StudyArmHandler(AbstractImportHandler):
    def __init__(self, study_arm):
        self.study_arm = study_arm

    def handle(self, df):
        df = df[['id']]
        df['studyarm_id'] = self.study_arm.id_as_str
        df = df.drop_duplicates()

        # drop cases that are already added to this arm.
        qs = self.study_arm.files.filter(id__in=list(df['id']))
        for q in qs:
            df = df.drop(df[df.case_id == q.id_as_str].index)  # TODO use pd isin ?
        if len(df.index) > 0:
            df = df.rename(columns={'id': 'file_id'})
            with io.StringIO() as buffer:
                df.to_csv(buffer, index=False)
                buffer.seek(0)
                with connection.cursor() as cursor:
                    cursor.copy_expert(
                        f'copy study_management_studyarm_files({",".join(df.columns)}) from stdin csv header',
                        buffer)
        logging.info('Files added to studyarm %s', self.study_arm)

    def handle_concept(self, df):
        df = df[['code_id']]
        df['study_id'] = self.study_arm.study.id_as_str
        df = df.drop_duplicates()
        # drop concepts that are already added to this study.
        qs = self.study_arm.study.codes.filter(id__in=list(df['code_id']))
        for q in qs:
            df = df.drop(df[df.code_id == q.id_as_str].index)
        if len(df.index) > 0:
            with io.StringIO() as buffer:
                df.to_csv(buffer, index=False)
                buffer.seek(0)
                with connection.cursor() as cursor:
                    # study_management_study_concepts
                    cursor.copy_expert(
                        f'copy {Study.codes.through.objects.model._meta.db_table}({",".join(df.columns)}) from stdin csv header',
                        buffer)
            logging.info('Terms added to study %s', self.study_arm.study)


class TileSetHandler(AbstractImportHandler):
    def __init__(self, tileset):
        self.tileset = tileset

    def handle_concept(self, df):
        df = df[['code_id']]
        df['tileset_id'] = self.tileset.id_as_str
        df = df.drop_duplicates()

        with io.StringIO() as buffer:
            df.to_csv(buffer, index=False)
            buffer.seek(0)
            with connection.cursor() as cursor:
                # tile_management_tileset_terms
                cursor.copy_expert(
                    f'copy {TileSet.terms.through.objects.model._meta.db_table}({",".join(df.columns)}) from stdin csv header',
                    buffer)
        logging.info('Terms added to study %s', self.tileset)

    def handle(self, df):
        df = df[['id']]
        df = df.rename(columns={'id': 'file_id'})
        df['fileset_id'] = self.tileset.id_as_str

        with io.StringIO() as buffer:
            df.to_csv(buffer, index=False)
            buffer.seek(0)
            with connection.cursor() as cursor:
                # fileset_fileset_files
                cursor.copy_expert(
                    f'copy {FileSet.files.through.objects.model._meta.db_table}({",".join(df.columns)}) from stdin csv header',
                    buffer)
        logging.info('Files added to tileset %s', self.tileset)


class MetadataImporter:

    def __init__(self, created_by, import_folder, origin=None, handlers=None,
                 qs_file=None, concept_mapping=None):
        if handlers is None:
            handlers = []
        self.created_by: Profile = created_by
        self.origin: Profile = get_user_node() if origin is None else origin
        self.case_cache = {}
        self.file_cache = {}
        self.terms_cache = {}
        self.codesystem_cache = {}
        self.import_folder = import_folder
        self.handlers = handlers
        self.qs_file = qs_file
        self.now = timezone.now().isoformat()
        self.concept_mapping = concept_mapping

        if self.qs_file is None:
            self.qs_file = File.objects.for_user(created_by)

    def create_file_cache(self):
        identifiers = []
        if 'identifier' in self.df.columns:
            identifiers = list(self.df['identifier'].dropna())
        if 'originating_from_id' in self.df.columns:
            identifiers += list(self.df['originating_from_id'].dropna())

        qs = File.objects.filter(created_by=self.created_by, identifier__in=identifiers)
        self.file_cache = {f.identifier: f for f in qs}

    def create_case_cache(self):
        if not 'case_id' in self.df.columns: return
        cases = list(self.df['case_id'].drop_duplicates())
        # TODO investigate if a condition with study=XY is required here.
        qs = Case.objects.filter(name__in=cases,
                                 created_by=self.created_by)  # only allow a user to add files to a case that he possesses.
        self.case_cache = {c.name: c for c in qs}

        # create the cases that are not persisted database yet
        if len(cases) != len(self.case_cache):
            diff = set(cases).difference(set(self.case_cache.keys()))
            diff = list(filter(lambda e: len(str(e).strip()) > 0, diff))
            with io.StringIO() as buffer:
                fieldnames = ['id', 'date_created', 'last_modified', 'identifier', 'name', 'created_by_id', 'origin_id']
                writer = csv.writer(buffer)
                writer.writerow(fieldnames)
                created_by_id = self.created_by.id_as_str
                origin_id = self.origin.id_as_str
                writer.writerows(
                    [[str(uuid.uuid4()), self.now, self.now, identifier.create_random('case'), str(d), created_by_id,
                      origin_id] for d
                     in diff])
                buffer.seek(0)
                with connection.cursor() as cursor:
                    cursor.copy_expert(
                        f'copy {Case.objects.model._meta.db_table}({",".join(fieldnames)}) from stdin csv header NULL as \'null\'',
                        buffer
                    )
                # add new cases to cache
                for case in Case.objects.filter(name__in=cases):
                    self.case_cache[case.name] = case

    def map_originating_from_id(self):
        if not 'originating_from_id' in self.df.columns: return

        def fn(e):
            if e not in self.file_cache:
                return None
            c = self.file_cache.get(e, None)
            return c.id_as_str if c is not None else c

        self.df['originating_from_id'] = self.df['originating_from_id'].apply(fn)

    def map_case_id(self):
        if not 'case_id' in self.df.columns and 'originating_from_id' not in self.df.columns: return

        def fn(e):
            if 'case_id' in e:
                case_id = str(e['case_id'])

                # if ('identifier' in e and len(e['identifier'].strip()) > 0 and self.origin == self.created_by):
                #     return None

                # if identifier is present and origin == created_by the file must not be added, so no file mapping.
                # if ('identifier' in e and len(e['identifier'].strip()) > 0 and self.origin == self.created_by) or \
                #     case_id not in self.case_cache or \
                #     len(case_id) == 0:
                #     return None
                # TODO if case_id is empty or not given and src is, get the case from src
                c = self.case_cache.get(case_id, None)
                return c.id_as_str if c is not None else None

            f = self.file_cache.get(e['originating_from_id'], None)
            if f is not None:
                return f.case.id_as_str
            return None

        self.df['case_id'] = self.df.apply(fn, axis=1)

    def add_id_column(self):
        def fn(e):
            if 'identifier' in e:
                identifier_ = e['identifier']
                if len(identifier_) > 0 and identifier_ in self.file_cache:
                    return self.file_cache[identifier_].id_as_str
            return str(uuid.uuid4())

        self.df['id'] = self.df.apply(fn, axis=1)

    def create_codes(self, terms):
        # TODO replace stuff with self.concept_mapping
        terms['codes'] = terms['codes'].apply(lambda e: e.split(','))
        terms = terms.explode('codes')
        terms = terms.loc[terms['codes'].str.len() > 0]  # only rows that actually have codes
        if len(terms.index) == 0:
            return

        # def term_in_mapping(codesystem_uri, term):
        #     return self.con
        #     if f'{codesystem_uri}#{term}' in self.concept_mapping.keys():
        #         pass

        def fn(c):
            if not c in self.terms_cache:
                if len(c.strip()) == 0:
                    return None
                o, t = c.split('#')
                if o not in self.codesystem_cache:
                    qs = CodeSystem.objects.filter(uri=o)
                    if not qs.exists():
                        cs = CodeSystem.objects.create(created_by=self.created_by, origin=self.origin, name=o, uri=o)
                    else:
                        cs = qs.first()
                    self.codesystem_cache[o] = cs

                mapped_code = self.concept_mapping.get(c)
                if mapped_code is not None:
                    concept = Code.objects.get(pk=mapped_code)
                else:
                    concept, _ = Code.objects.get_or_create(codesystem=self.codesystem_cache[o],
                                                            codesystem_name=self.codesystem_cache[o].name,
                                                            code=t,
                                                            created_by=self.created_by,
                                                            origin=self.origin)
                self.terms_cache[c] = concept
            return self.terms_cache[c].id_as_str

        terms['codes'] = terms['codes'].apply(fn)

        with io.StringIO() as buffer:
            terms = terms.rename(columns={'codes': 'code_id', 'id': 'file_id'})
            terms.to_csv(buffer, index=False)
            buffer.seek(0)
            with connection.cursor() as cursor:
                cursor.copy_expert(
                    f'copy {File.codes.through.objects.model._meta.db_table}({",".join(terms.columns)}) from stdin csv header NULL as \'null\'',
                    buffer
                )

        for handler in self.handlers:
            handler.handle_concept(terms)

    def drop_with_identifier(self, df):
        if 'identifier' in df.columns:
            return df.loc[~(df['identifier'].str.len() > 0 | df['identifier'].notna()),
                   :]  # empty string has higher precedence than null
        return df

    def create_files(self):
        # TODO if row already has an identifier, do not import that row
        # TODO cut out any field that is no column to prevent errors
        with io.StringIO() as buffer:
            # only use the rows that do not have an identifier = should be inserted
            df = self.drop_with_identifier(self.df)
            # add identifier here after dropping all rows that already contain an identifier provided by the user
            if len(df.index) > 0:
                if not 'identifier' in self.df.columns:
                    self.df['identifier'] = [identifier.create_random('file') for _ in range(len(self.df.index))]
                else:
                    cond = ~(df['identifier'].str.len() > 0 | df['identifier'].notna())
                    self.df['identifier'][cond] = self.df['identifier'][cond].apply(
                        lambda e: identifier.create_random('file'))

                df['identifier'] = self.df['identifier']
                df['import_folder_id'] = self.import_folder.id_as_str
                # TODO add importfolder here?
                df.to_csv(buffer, index=False, na_rep='null')
                buffer.seek(0)
                with connection.cursor() as cursor:
                    cursor.copy_expert(
                        f'copy {File.objects.model._meta.db_table}({",".join(self.df.columns)}) from stdin csv header NULL as \'null\'',
                        buffer
                    )

    def prepare_date_columns(self):
        self.df['date_created'] = self.now
        self.df['last_modified'] = self.now

    def prepare_column_imported(self):
        self.df['imported'] = False

    def create_metadata(self, df):
        df = df.rename(columns={'id': 'file_id'})
        df['id'] = df.apply(lambda e: str(uuid.uuid4()), axis=1)
        df['date_created'] = self.now
        df['last_modified'] = self.now
        df['metadata'] = df['metadata'].apply(lambda e: e.split(','))
        df['metadata'] = df['metadata'].explode('metadata')

        def fn(e):
            if '=' in e['metadata']:
                k, v = e['metadata'].split('=')
                e['system'] = k
                e['value'] = v
                e['readable'] = None
            return e

        col_file_id = df['file_id']
        df = df.apply(fn, axis=1)
        df = df.drop(['metadata', 'file_id'], axis=1)
        if not 'system' in df.columns:
            return
        with io.StringIO() as buffer:
            if len(df.index) > 0:
                df.to_csv(buffer, index=False, na_rep='null')
                buffer.seek(0)
                with connection.cursor() as cursor:
                    cursor.copy_expert(
                        f'copy {Annotation.objects.model._meta.db_table}({",".join(df.columns)}) from stdin csv header NULL as \'null\'',
                        buffer
                    )

        df = df[['id']]
        df = df.rename(columns={'id': 'annotation_id'})
        df['file_id'] = col_file_id
        with io.StringIO() as buffer:
            if len(df.index) > 0:
                df.to_csv(buffer, index=False, na_rep='null')
                buffer.seek(0)
                with connection.cursor() as cursor:
                    cursor.copy_expert(
                        f'copy {File.annotations.through.objects.model._meta.db_table}({",".join(df.columns)}) from stdin csv header NULL as \'null\'',
                        buffer
                    )

    def run(self, file: Path):
        df = pd.read_csv(file, na_filter=False)
        self.df = df.rename(columns={'src': 'originating_from_id', 'case': 'case_id', 'path': 'original_path'})
        self.create_file_cache()
        self.create_case_cache()
        self.prepare_column_imported()
        self.map_case_id()
        self.map_originating_from_id()
        self.add_id_column()
        self.prepare_date_columns()
        self.df['created_by_id'] = self.created_by.id_as_str
        self.df['origin_id'] = self.origin.id_as_str
        if 'name' in self.df.columns:
            self.df['original_filename'] = self.df['name']

        has_metadata = 'metadata' in self.df.columns
        has_concepts = 'codes' in self.df.columns
        if has_concepts:
            terms = self.drop_with_identifier(self.df)[['id', 'codes']]
            self.df = self.df.drop(['codes'], axis=1)

        if has_metadata:
            col_metadata = df['metadata']
            self.df = self.df.drop(['metadata'], axis=1)

        self.create_files()

        if has_metadata:
            df = self.df[['id']]
            df['metadata'] = col_metadata
            self.create_metadata(df)

        if has_concepts:
            self.create_codes(terms)

        for handler in self.handlers:
            handler.handle(self.df)

    #     # TODO run in an transaction
    #     # TODO raise exception on error


class MetadataUpdater:

    def run(self, csv_file: Path):

        with csv_file.open() as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            key_identifier = 'identifier'
            if key_identifier not in fieldnames:
                raise ValueError(f'identifier not found in fieldnames: {fieldnames}')

            key_case_identifier = 'case_identifier'
            has_case_identifier = key_case_identifier in reader.fieldnames
            key_size = 'size'
            has_size = key_size in reader.fieldnames
            key_terms = 'terms'
            has_terms = key_terms in reader.fieldnames
            key_name = 'name'
            has_name = key_name in reader.fieldnames
            key_original_filename = 'original_filename'
            has_original_filename = key_original_filename in reader.fieldnames
            key_original_path = 'original_path'
            has_original_path = key_original_path in reader.fieldnames
            key_path = 'path'
            has_path = key_path in reader.fieldnames

            for row in reader:
                file: QuerySet[File] = File.objects.filter(identifier=row[key_identifier])
                if not file.exists():
                    continue
                file: File = file.first()

                if has_case_identifier:
                    case = Case.objects.filter(identifier=row[key_case_identifier])
                    if case.exists():
                        file.case = case.first()

                if not file.imported:
                    if has_size:
                        file.size = row[key_size]

                    # if a path is provided also set the file as imported
                    if has_path:
                        path = row[key_path]
                        if len(path.strip()) > 0:
                            file.path = path
                            file.imported = True

                if has_name:
                    file.name = row[key_name]

                if has_original_filename:
                    file.original_filename = row[key_original_filename]

                if has_original_path:
                    file.original_path = row[key_original_path]

                if has_terms:
                    terms = row[key_terms].split(',')
                    file.codes.clear()
                    code_cache: Dict[str, Code] = {}
                    for t in terms:
                        parts = t.split('#')
                        if len(parts) != 2:
                            continue
                        cached = code_cache.get(t)
                        if cached is None:
                            code_qs = Code.objects.filter(code=parts[1], codesystem__uri=parts[0])
                            if code_qs.exists():
                                code_cache[t] = code_qs.first()

                        cached = code_cache.get(t)
                        if cached is not None:
                            file.codes.add(cached)

                file.save()
