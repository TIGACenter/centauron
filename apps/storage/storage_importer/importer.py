import csv
import io
import json
import logging
import os
import random
import shutil
import string
import uuid
from pathlib import Path

import magic
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction, connection

from apps.core import identifier
from apps.core.models import Annotation
from apps.project.models import Project, FilePermission
from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.storage.storage_importer.models import ImportFolder
from apps.user.user_profile.models import Profile

User = get_user_model()


class MetadataImporter:
    def __init__(self, import_folder: ImportFolder, **kwargs):
        '''

        :param import_folder: the instance of the import folder from which this file will be imported.
        :param kwargs:
        '''
        self.import_folder = import_folder
        self.flush_every = settings.IMPORTER_FLUSH_EVERY

    # def run_from_string(self, csv: str, origin: User):
    #     with tempfile.NamedTemporaryFile('rb+') as f:
    #         f.write(csv)
    #         f.seek(0)
    #         self.run(f.name, origin=origin)

    def run(self, csv_path: Path, *, project: Project, created_by: Profile, progress_callback=None) -> list[str]:
        '''
        Imports metadata from a csv file. File needs to have the following columns: id, name, case, metadata, size, content_type
        Columns:
            * id = string representation of the identifier
            * name = file name with extension
            * case = the string representation of the case identifier
            * metadata = a json object that contains any arbitrary metadata as key-value. no arrays excepted.
        :param csv_path:
        :param created_by:
        :param origin:
        :return: A list that contains the id as string of the imported files.
        '''
        with csv_path.open() as f:
            # manually splitting here not optimal. windows has different clrf than unix. use this only for DEV
            reader = csv.DictReader(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            des = []
            ids = []
            lst = list(reader)
            total = len(lst)
            with transaction.atomic():
                for idx, entry in enumerate(lst):
                    if progress_callback is not None:
                        progress_callback((idx + 1) / total)
                    size = entry.get('size', 0)
                    if len(size) == 0: size = 0

                    if idx > 0 and idx % 10_000 == 0:
                        logging.info('%s entries imported.', idx)

                    provided_case = entry.get('case', None)
                    if provided_case is None or len(provided_case.strip()) == 0:
                        id = identifier.create_random('file')
                    else:
                        id = identifier.from_string(provided_case)
                        if id is None:
                            logging.warning('Invalid identifier %s', provided_case)
                            break
                    qs_case_exists = Case.objects.filter(projects=project,
                                                         identifier=id)

                    if not qs_case_exists.exists():
                        case_name = entry.get('name').split('.')[0]  # case name is the file name
                        case = Case.objects.create(name=case_name, identifier=id,
                                                   origin=created_by)  # TODO how to set origin here? is created_by correct?
                        case.projects.add(project)
                    else:
                        case = qs_case_exists.first()

                    d = File(created_by=created_by,
                             name=entry.get('name'),
                             origin=created_by,  # TODO how to set origin here? is created_by correct?
                             import_folder=self.import_folder,
                             content_type=entry.get('content_type', ''),
                             case=case,
                             original_filename=entry.get('name'),
                             original_path=entry.get('path'),
                             size=int(size),
                             identifier=identifier.create_random('file'))
                    d.save()

                    metadata = json.loads(entry.get('metadata', '{}'))
                    for key, value in metadata.items():
                        a = Annotation.objects.create(system=key, value=value)
                        d.annotations.add(a)

                    # i.save()
                    ids.append(d.id_as_str)
                    # d.add_identifier(i)
                    # m2m = File.identifier.through(file_id=d.id, identifier_id=i.id)
                    # des_2_i.append(m2m)
                    # des.append(d)

            logging.info('Start creating objects.')
            # File.objects.bulk_create(des)
            # Identifier.objects.bulk_create(identifiers)
            # Identifier.files_identifier.through.bulk_insert(des_2_i)
            logging.info('Done creating %s objects.', len(des))
            return ids


class FileImporter:

    def __init__(self, import_dir: Path, data_dir: Path, **kwargs):
        self.import_dir = import_dir
        self.data_dir = data_dir
        self.flush_every = kwargs.get('flush_every', 500_000)

    def run(self):
        """
        Traverses the import folder recursively. If a metadata.json file exists, all files listed in this file are imported and matched with their already imported metadata in the database.
        :return:
        """
        # from apps.files.tasks import send_webhook_files_imported

        for folder in ImportFolder.objects.get_ready_for_import():
            imported = self.import_from_import_folder(folder)
        #     if imported is not None:
        #         send_webhook_files_imported.delay(folder.id_as_str)

    def import_from_import_folder(self, folder: ImportFolder, **kwargs):
        if not folder.ready_for_import():
            logging.warning('Folder %s not ready for importing yet. Skipping.', folder)
            return None
        logging.info('Importing from %s', folder)
        folder.importing = True
        folder.save(update_fields=['importing'])
        dst = folder.path_in_data_dir / str(uuid.uuid4())
        dst.parent.mkdir(parents=True, exist_ok=True)
        # use temporary not imported folder to speed up moving the registered files
        not_imported_folder_tmp = settings.STORAGE_IMPORT_DIR / (
            str(folder.not_imported_folder.parent.relative_to(settings.STORAGE_IMPORT_DIR)) + '.notimported.ignore')
        # logging.debug('tmp not imported folder is {}', not_imported_folder_tmp)
        with (transaction.atomic()):
            # iterate over file and check if announced files are actually there and register them
            directories = []

            # create pg tmp table to write data in
            # then import data into tmp table with copy from csv
            # then update file table with new data
            # TODO set content type if null
            cursor = connection.cursor()
            tbl_name = ''.join(random.choice(string.ascii_uppercase) for _ in range(5))

            cursor.execute(
                f'create temp table {tbl_name} (original_path text, path text, size int8, content_type text)')

            memory_file = io.StringIO()
            writer = csv.writer(memory_file)
            csv_header = ['original_path', 'path', 'size', 'content_type']
            writer.writerow(csv_header)
            INTERVAL = 10_000
            for idx, file in enumerate(self.walk(folder.import_dir)):
                if file.absolute() == folder.import_dir.absolute():
                    continue

                if file.is_dir():
                    continue

                logging.info(f'[Importer] Found file: {file}')

                if idx % INTERVAL == 0:
                    logging.info(idx)
                # logging.debug(file)

                path = file.relative_to(folder.import_dir)
                # most of the files will exist, so try catch is faster than query.exist()
                try:
                    s = str(path)
                    kw = {}
                    mimetype = magic.from_file(file, mime=True)
                    new_path = settings.STORAGE_DATA_DIR / f'{uuid.uuid4()}-{file.name}'
                    # moving the files faste than shutil.move but fallback to it if not implemented for the used file system.
                    try:
                        logging.info(f'Import file {file} -> {new_path}')
                        os.rename(str(file.resolve()), str(new_path.resolve()))
                    except Exception:
                        logging.info(f'{file} fall back to shutil.move')
                        shutil.move(file, new_path)
                    kw['path'] = str(new_path.relative_to(settings.STORAGE_DATA_DIR))
                    writer.writerow([s, kw['path'], new_path.stat().st_size, mimetype])
                except shutil.Error as e:
                    logging.error('File %s could not be imported.', file)
                    logging.exception(e)
                    not_imported_folder_tmp.mkdir(exist_ok=True)
                    dst_mv = not_imported_folder_tmp / file.relative_to(folder.import_dir)
                    dst_mv.parent.mkdir(parents=True, exist_ok=True)
                    logging.debug('Moving file %s to %s', file, dst_mv)
                    shutil.move(file, dst_mv)
                    continue

            # do not catch exceptions here. transaction will be rolled back if any exception is thrown
            memory_file.seek(0)
            cursor.copy_expert(f'copy {tbl_name}({",".join(csv_header)}) from stdin csv header NULL as \'null\'',
                               memory_file)
            memory_file.close()

            # do the update
            sql = f'update storage_file set imported = true, path = {tbl_name}.path, content_type = {tbl_name}.content_type, size = {tbl_name}.size from {tbl_name} where storage_file.imported = %s and storage_file.import_folder_id = %s and {tbl_name}.original_path = storage_file.original_path'
            a = cursor.execute(sql, (False, folder.id_as_str,))
            cursor.execute(f'drop table {tbl_name};')
            cursor.close()

            if not_imported_folder_tmp.exists():
                logging.debug('Moving file %s to %s', not_imported_folder_tmp, folder.not_imported_folder)
                # move files back from tmp ignore to real ignore
                shutil.move(not_imported_folder_tmp, folder.not_imported_folder)

            for d in directories:
                if d.exists():
                    logging.debug('Deleting empty dir %s.', d)
                    shutil.rmtree(d)

        # this is a bit slow for a large number of files but whatever. this could be potentially refactored to a csv import into sql
        # this updates all FilePermission objects and sets the file as imported
        qs = File.objects.filter(import_folder=folder)
        for f in qs:
            FilePermission.objects.filter(file_id=f.pk, user_id=f.created_by_id).update(imported=f.imported)

        folder.imported = not File.objects.filter(import_folder=folder, imported=False).exists()
        folder.importing = False
        folder.save(update_fields=['imported', 'importing'])

        logging.info('Importing folder %s done.', folder)
        return True

    def walk(self, path: Path):
        if path.exists():
            yield path.resolve()  # yield folder path
            if path.exists():
                for p in path.iterdir():
                    if not p.name.endswith('.ignore') and not p.name.endswith('.notimported'):
                        if p.is_dir():
                            if p.exists():
                                yield from self.walk(p)
                                continue
                        if p.exists():
                            yield p.resolve()
