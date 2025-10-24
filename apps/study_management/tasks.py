import csv
import logging
import shutil

from django.conf import settings
from django.db.models import QuerySet

from apps.storage.models import File
from apps.study_management.models import StudyArm
from config import celery_app

EXPORT_ARM_FILES_COLUMNS = ['id', 'identifier', 'case', 'case_identifier', 'name', 'path', 'original_path', 'original_filename', 'origin',
                            'imported', 'size', 'terms']


def export_arm_files_column_values(arm_pk):
    qs: QuerySet[File] = File.objects.filter(study_arms=arm_pk).prefetch_related('annotations',
                                                                                 'origin',
                                                                                 'case',
                                                                                 'codes')
    for f in qs:
        yield [f.id_as_str, f.identifier, f.case.name, f.case.identifier, f.name, f.path, f.original_path, f.original_filename,
               f.origin.identifier, f.imported, f.size, ','.join(f.code_list_identifier_rep())]


@celery_app.task
def export_arm_files_to_csv(arm_pk: str, dst: str):
    arm = StudyArm.objects.get(pk=arm_pk)
    logging.info('Start exporting study arm files to %s', dst)
    dst_org = dst
    dst = settings.STORAGE_EXPORT_DIR / f'{dst}.exporting'

    with dst.open('w') as f:
        writer = csv.writer(f)
        writer.writerow(EXPORT_ARM_FILES_COLUMNS)
        writer.writerows([f for f in export_arm_files_column_values(arm_pk)])

    shutil.move(dst, settings.STORAGE_EXPORT_DIR / dst_org)
    logging.info('Done exporting.')


@celery_app.task
def export_imported_files_to_csv(arm_pk: str, dst: str):
    arm = StudyArm.objects.get(pk=arm_pk)
    logging.info('Start exporting study arm files to %s', dst)
    dst_org = dst
    dst = settings.STORAGE_EXPORT_DIR / f'{dst}.exporting'

    with dst.open('w') as f:
        writer = csv.writer(f)
        writer.writerow(['identifier'])
        qs = File.objects.filter(study_arms=arm, imported=True).values_list('identifier', flat=True)
        writer.writerows([[f] for f in qs])

    shutil.move(dst, settings.STORAGE_EXPORT_DIR / dst_org)
    logging.info('Done exporting.')
