from django.db import models

from apps.core.models import CreatedByMixin, OriginMixin, IdentifieableMixin, BaseResource


class FileSet(CreatedByMixin, OriginMixin, IdentifieableMixin, BaseResource):
    name = models.CharField(max_length=100)
    files = models.ManyToManyField('storage.File', blank=True, related_name='filesets')

    files_count = models.IntegerField(default=0)
    files_imported_count = models.IntegerField(default=0)
    files_total_size = models.BigIntegerField(default=0)
    files_imported_total_size = models.BigIntegerField(default=0)

    def __str__(self):
        return f'{self.name}'


