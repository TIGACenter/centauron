import csv
import tempfile
from pathlib import Path

from django.db.models import QuerySet

from apps.blockchain.messages import CreateMessage, Object
from apps.blockchain.models import Log
from apps.project.models import Project, FilePermission
from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.terminology.models import CodeSet, Code
from apps.user.user_profile.models import Profile
from config import celery_app


@celery_app.task
def import_files_into_project(file_ids: list[str], project_id: str):
    project = Project.objects.get(pk=project_id)
    files = File.objects.filter(id__in=file_ids)
    for f in files:
        project.files.add(f)


@celery_app.task
def import_csv(path: str, project_id: str):
    project = Project.objects.get(pk=project_id)

    with Path(path).open() as f:
        reader = csv.DictReader(f)

        # prefer column id over identifier
        if 'id' in reader.fieldnames:
            ids = [r['id'].strip() for r in reader]
            kw = 'id__in'
        elif 'identifier' in reader.fieldnames:
            ids = [r['identifier'].strip() for r in reader]
            kw = 'identifier__in'

        kwargs = {kw: ids}
        qs_files = File.objects.filter(**kwargs)
        qs_cases = Case.objects.filter(files__in=qs_files)

        for f in qs_files:
            fp = FilePermission.objects.create(user=f.created_by, project=project, file=f, imported=f.imported)
            project.filepermission_set.add(fp)
        project.cases.add(*qs_cases)

        # add codes from files to project
        qs_codes = Code.objects.filter(id__in=qs_files.values_list('codes', flat=True).distinct())
        has_codes = qs_codes.exists()
        if has_codes:
            if not project.has_codeset:
                project.codeset = CodeSet.objects.create()
                project.save(update_fields=['codeset'])

            project.codeset.codes.add(*qs_codes)

    # broadcast a message that data was added to the project
    actor = project.created_by.to_actor()
    msg = CreateMessage(actor=actor, object=Object(value=ids, model="slide"),
                        context={'project': project.to_identifiable()})
    Log.send_broadcast(msg)


def get_query(created_by, study_pk, terms_pk) -> QuerySet[Case]:
    qs = Case.objects.filter(created_by=created_by)
    if study_pk is not None:
        qs = qs.filter(files__study_arms__study_id=study_pk).distinct()

    if len(terms_pk) > 0:
        qs = qs.filter(files__codes__in=Code.objects.filter(pk__in=terms_pk)).distinct()
    return qs


@celery_app.task
def import_from_query(created_by_pk, project_pk, study_pk, term_pks):
    qs = get_query(Profile.objects.get(pk=created_by_pk), study_pk, term_pks)
    # write file identifiers to csv file and use the csv importer

    # open file in r+w mode
    with tempfile.NamedTemporaryFile('r+') as f:
        f.write('identifier\n')
        identifiers = list(qs.values_list('files__identifier', flat=True))
        for i in identifiers:
            f.write(i)
            f.write('\n')
        f.seek(0)
        import_csv(f.name, project_pk)
