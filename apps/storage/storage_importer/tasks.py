import logging
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model

from apps.computing.computing_executions.models import ComputingJobExecution
from apps.project.models import Project
from apps.storage.models import File
from apps.storage.storage_importer.importer import FileImporter, MetadataImporter
from apps.storage.storage_importer.models import ImportFolder, ImportJob
from apps.user.user_profile.models import Profile
from config import celery_app

User = get_user_model()


@celery_app.task(soft_time_limit=60 * 60 * 24 * 7)
def run_file_importer():
    importer = FileImporter(settings.STORAGE_IMPORT_DIR, settings.STORAGE_DATA_DIR)
    importer.run()


@celery_app.task
def import_single_file(file: File, path: Path, from_celery=True, remove_src_folder=True):
    import_folder = ImportFolder.objects.create(path=uuid.uuid4().hex + '.ignore')
    import_folder.import_dir.mkdir(parents=True, exist_ok=True)
    import_folder.files.add(file)
    # create subfolders
    dst = import_folder.import_dir / Path(file.original_path)
    logging.info('Creating folder: %s', dst.parent)
    dst.parent.mkdir(exist_ok=True, parents=True)
    try:
        logging.info('[start] Move %s -> %s', path, dst)
        shutil.move(path, dst)
        logging.info('[end] Move %s -> %s', path, dst)
    except Exception as e:  # FIXME this has to be in or moving won't work? WTF
        logging.exception(e)
    logging.info('remove_src_folder: %s', remove_src_folder)
    if remove_src_folder:
        # remove source dir
        logging.info('[start] Removing %s', path.parent)
        shutil.rmtree(path.parent)
        logging.info('[end] Removing %s', path.parent)

    # un-ignore import folder
    logging.info('Moving folder %s -> %s', str(import_folder.import_dir.resolve()),
                 str(settings.STORAGE_IMPORT_DIR / import_folder.path_without_ignore))
    shutil.move(import_folder.import_dir.resolve(), settings.STORAGE_IMPORT_DIR / import_folder.path_without_ignore)
    run_file_importer()
    if not from_celery:
        return import_folder.files.all()


@celery_app.task(soft_time_limit=60 * 60 * 24)  # 10_000 sec soft time limit
def import_computing_job_artefacts(computing_job_pk):
    job = ComputingJobExecution.objects.get(pk=computing_job_pk)

    import_folder = ImportFolder.objects.create(path=uuid.uuid4().hex + '.ignore')
    import_folder.import_dir.mkdir(parents=True, exist_ok=True)
    file_pks = job.artifacts.values_list('file', flat=True)
    import_folder.files.add(
        *File.objects.filter(id__in=file_pks))  # TODO check if this is fast enough or refactor to copy from cmd
    # create subfolders

    source = job.artifact_path
    destination = import_folder.import_dir

    for f in source.rglob('*'):
        if f.is_file() or f.is_dir():  # Process both files and directories
            # Calculate the relative path from the source root
            relative_path = f.relative_to(source)

            # Define the destination path, preserving the relative structure
            destination_path = destination / relative_path

            # Create any necessary directories in the destination path
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            logging.info(f'Moving {f} -> {destination_path}')
            # Move the file or directory to the destination
            shutil.move(str(f), str(destination_path))
    # for f in job.artifact_path.iterdir():
    #     shutil.move(f, import_folder.import_dir / f.name)

    # dst = import_folder.import_dir / Path(file.original_path)
    # dst.parent.mkdir(exist_ok=True, parents=True)
    # shutil.move(path, dst)
    # remove source dir
    # shutil.rmtree(path.parent)
    # if len(list(job.artifact_path.iterdir())) == 0:

    shutil.rmtree(job.artifact_path)

    # else:
    #     logging.warning('Folder {} is not empty, therefore not deleting.', job.artifact_path)

    # un-ignore import folder
    shutil.move(import_folder.import_dir.resolve(), settings.STORAGE_IMPORT_DIR / import_folder.path_without_ignore)
    run_file_importer()


@celery_app.task(bind=True)
def run_metadata_importer(self, *, project_id: str, profile_id: str, file_path: str):
    user = Profile.objects.get(pk=profile_id)
    csv_file_path = Path(file_path)

    project = Project.objects.get(pk=project_id)
    import_folder = ImportFolder.objects.create_for_project(project=project)
    importer = MetadataImporter(import_folder)
    import_job = ImportJob.objects.for_task_id(self.request.id, project)
    import_job.status = ImportJob.Status.STARTED
    import_job.file = str(csv_file_path.relative_to(settings.TMP_DIR))
    import_job.import_folder = import_folder
    import_job.save()

    def progress_callback(progress: float):
        import_job.progress = progress
        import_job.save(update_fields=['progress'])

    ids = importer.run(csv_file_path, project=project, created_by=user, progress_callback=progress_callback)

    import_job.status = ImportJob.Status.SUCCESS
    import_job.save()

    # TODO delete import folder again?

    return ids
