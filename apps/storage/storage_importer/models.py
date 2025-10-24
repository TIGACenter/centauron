import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from apps.core.models import Base
from apps.storage.models import File
from apps.storage.storage_importer.managers import ImportFolderManager, ImportJobManager
from apps.user.user_profile.models import Profile


class ImportFolder(Base):
    path = models.CharField(max_length=1000)
    imported = models.BooleanField(default=False)
    importing = models.BooleanField(default=False)
    project = models.ForeignKey('project.Project', on_delete=models.CASCADE, null=True,
                                related_name='import_folders',
                                blank=True)  # nullable so FileImporter can be used also for shared data outside of project scope
    study = models.ForeignKey('study_management.Study', on_delete=models.CASCADE, null=True,
                              related_name='import_folders', blank=True)
    study_arm = models.ForeignKey('study_management.StudyArm', on_delete=models.CASCADE, null=True,
                                  related_name='import_folders', blank=True)
    objects = ImportFolderManager()

    def ready_for_import(self):
        # the folder is only ready for import of the importing application removed the .ignore extension.
        # check if already imported
        if self.imported: return False
        # check if not exists and a folder with the same name but without the .ignore extension exists.
        is_ready = (settings.STORAGE_IMPORT_DIR / self.path_without_ignore).exists()  # and not self.import_dir.exists()
        if is_ready and self.path != self.path_without_ignore:
            self.path = self.path_without_ignore
            self.save()

        return is_ready

    @property
    def path_without_ignore(self):
        if self.path.endswith('.ignore'):
            return self.path[:-len('.ignore')]
        return self.path

    @property
    def path_in_data_dir(self):
        return settings.STORAGE_DATA_DIR / self.path_without_ignore

    @property
    def import_dir(self) -> Path:
        return (settings.STORAGE_IMPORT_DIR / self.path).resolve()

    @property
    def not_imported_folder(self) -> Path:
        return settings.STORAGE_IMPORT_DIR / self.path_without_ignore / '.notimported'

    def save(
        self, **kwargs
    ):
        super(ImportFolder, self).save(**kwargs)
        if not self.import_dir.exists():
            self.import_dir.mkdir(parents=True)

    def __str__(self):
        return str(self.import_dir.resolve())

    @staticmethod
    def create():
        return ImportFolder.objects.create(path=str(uuid.uuid4()))

    @staticmethod
    def create_for_study_arm(study_arm):
        i_f = ImportFolder.objects.create_for_study_arm(study_arm)
        files = study_arm.files.filter(imported=False)
        paths = files.values_list('original_path', flat=True)
        paths_to_create = set()
        for p in paths:
            paths_to_create.add(Path(p).parent)

        for p in paths_to_create:
            a = i_f.import_dir / p
            a.mkdir(parents=True, exist_ok=True)

        files.update(import_folder=i_f)
        return i_f

class ImportJob(Base):
    objects = ImportJobManager()

    class Status(models.TextChoices):
        FAILURE = 'FAILURE'
        PENDING = 'PENDING'
        STARTED = 'STARTED'
        SUCCESS = 'SUCCESS'

    celery_task_id = models.CharField(max_length=50, unique=True)
    status = models.CharField(choices=Status.choices, default=Status.PENDING, max_length=15)
    progress = models.FloatField(default=0.0)
    file = models.CharField(max_length=500)
    project = models.ForeignKey('project.Project', on_delete=models.CASCADE, null=True)
    study = models.ForeignKey('study_management.Study', on_delete=models.CASCADE, null=True)
    import_folder = models.ForeignKey(ImportFolder, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f'{self.file}: {self.status} ({self.progress * 100}%)'
