import csv
import json
import logging
from pathlib import Path

from django.contrib.auth.models import User
import logging

from apps.core.identifier import IDENTIFIER_FORMAT, create_identifier
from apps.project.models import Project
from apps.project.project_case.models import Case
from apps.storage.models import File


class MetadataImporter:
    flush_every = 100_000

    def run(self, created_by: User, project: Project, file: Path):
        '''
        TODO this method may not be very efficient for importing a large batch of files with len(files) > 50_000
        '''
        with file.open('r') as f:
            # import here: case, file_identifier, filename, metadata
            # this way, we can store multiple files for a single case
            # assumption: file metadata was already imported into storage service and identifier are known by exporting from storage service.
            reader = csv.DictReader(f, delimiter=';', fieldnames=['id', 'name', 'case', 'metadata'])
            next(reader)  # skip header row
            data = []
            for row in reader:
                data.append([row['id'], row['name'], row['case'], row['metadata']])  # explicit order
            identifier = [r[0] for r in data]
            logging.debug('Requesting paths from storage service.')
            # request the paths and from storage service.
            # file metadata was already imported into storage service before.
            # here: checking if a file exists in storage service for provided identifier
            # if so, import into project, if not then ignore provided identifier.
            # TODO paths = storage_service.get_paths_from_identifier(identifier, jwt)
            logging.debug('Paths from storage service received.')
            get_csv_row = lambda identifier: \
                [row for row in data if row[0] == IDENTIFIER_FORMAT.format(identifier.system, identifier.value)]
            for i, path in enumerate(paths):
                # TODO add metadata to file object. maybe as annotations?? each key in json object could be an annotation.
                identifier_ = path['identifier']
                file_already_exist_in_project = False

                # if file is already in project, skip the import
                for i in identifier_:
                    if not file_already_exist_in_project:
                        file_already_exist_in_project = File.objects.filter(projects__in=[project],
                                                                            identifier=i).exists()
                    else:
                        break
                ignore_file = False
                if file_already_exist_in_project:
                    logging.warning('Ignoring file [%s] as it already exists in project [%s].', i, project)
                    ignore_file = True
                d = None
                # identifiers = []
                # for i in identifier_:
                #     id = Identifier(**i)
                #     identifiers.append(id)
                #     d = get_csv_row(id)

                if not ignore_file:
                    print(d)
                    if d[2] is not None and len(d[2].strip()) > 0:
                        case_identifier_value = f'case::{d[2]}'.strip()
                        case = Case.objects.filter(identifier__value=case_identifier_value)
                        if not case.exists():
                            case = Case.objects.create(name=d[2].strip(), created_by=created_by,
                                                       identifier=create_identifier(case_identifier_value))
                        else:
                            case = case.first()
                        case.projects.add(project)

                    file = File.objects.create(created_by=created_by,
                                               case=case,
                                               identifier=identifier_,
                                               path=path['original_path'],
                                               original_filename=path['original_filename'])
                else:
                    qs = File.objects.filter(projects__in=[project],
                                             identifier=i)
                    print(qs)
                    file: File = qs.first()
                    metadata_json = json.loads(d[3])
                    for k, v in metadata_json.items():
                        a, created = file.annotations.get_or_create(system=k)
                        a.value = v
                        a.save()

                        if created:
                            file.annotations.add(a)

        logging.info('Importing metadata done.')
