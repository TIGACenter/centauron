import traceback
from pathlib import Path
from typing import Dict

from apps.storage.models import File
from apps.storage.storage_importer.models import ImportFolder
from apps.study_management.import_data.importer import MetadataImporter, StudyArmHandler, TileSetHandler, \
    MetadataUpdater
from apps.study_management.import_data.models import ImportJob
from apps.study_management.tile_management.models import TileSet
from config import celery_app


@celery_app.task(bind=True)
def run_importer(self, import_job_pk: str, concept_mapping: Dict[str, str]):
    job: ImportJob = update_and_return_import_job(import_job_pk, self.request.id)
    # call importer
    import_folder = ImportFolder.objects.create_for_study(job.study_arm.study)
    handler = StudyArmHandler(job.study_arm)
    try:
        MetadataImporter(job.created_by, import_folder, handlers=[handler], origin=job.created_by,
                         concept_mapping=concept_mapping).run(job.file_path)
        job.status = ImportJob.Status.SUCCESS
        job.save(update_fields=['status'])
    except Exception as e:
        job.status = ImportJob.Status.FAILED
        job.message = traceback.format_exc()
        job.save(update_fields=['status', 'message'])
        traceback.print_exception(e)


def update_and_return_import_job(pk, task_id):
    job: ImportJob = ImportJob.objects.get(pk=pk)
    # except ImportJob.DoesNotExist:
    job.celery_task_id = task_id
    job.status = ImportJob.Status.RUNNING
    job.save(update_fields=['status', 'celery_task_id'])
    return job


@celery_app.task(bind=True, soft_time_limit=60 * 60 * 24)
def run_importer_tileset(self, import_job_pk: str, tileset_pk: str):
    job: ImportJob = update_and_return_import_job(import_job_pk, self.request.id)
    # call importer
    import_folder = ImportFolder.objects.create_for_study(job.study_arm.study)
    handler = TileSetHandler(TileSet.objects.get(pk=tileset_pk))

    qs = File.objects.for_user(job.created_by).filter(filesets=tileset_pk)
    MetadataImporter(job.created_by, import_folder, handlers=[handler], qs_file=qs).run(job.file_path)

    job.status = ImportJob.Status.SUCCESS
    job.save(update_fields=['status'])


@celery_app.task
def run_metadata_updater(file_path: str):
    MetadataUpdater().run(Path(file_path))
