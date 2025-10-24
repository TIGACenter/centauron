import uuid

from django.db import models
from django.utils.text import slugify

from apps.project.models import Project
from apps.study_management.models import Study, StudyArm


class ImportFolderManager(models.Manager):

    def get_ready_for_import(self):
        # an importfolder is ready to import if not all files were imported yet.
        return self.filter(imported=False, importing=False)

    def create_for_project(self, project: Project):
        from apps.storage.storage_importer.models import ImportFolder
        path = f'{uuid.uuid4()}.ignore'
        return ImportFolder.objects.create(project=project, path=path)

    def create_for_study(self, study: Study):
        from apps.storage.storage_importer.models import ImportFolder
        path = f'{slugify(study.name)}-{uuid.uuid4()}.ignore'
        return ImportFolder.objects.create(study=study, path=path)

    def create_for_study_arm(self, study_arm: StudyArm):
        from apps.storage.storage_importer.models import ImportFolder
        path = f'{slugify(study_arm.name)}-{uuid.uuid4()}.ignore'
        return ImportFolder.objects.create(study_arm=study_arm, path=path)


class ImportJobManager(models.Manager):

    def for_task_id(self, task_id, project):
        qs = self.filter(celery_task_id=task_id)
        if not qs.exists():
            return self.create(celery_task_id=task_id, project=project)
        return qs.first()
