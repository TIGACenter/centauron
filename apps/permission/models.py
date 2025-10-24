import csv
import io
import random
import string
import uuid
from typing import List

from django.db import models, connection
from django.db.models import UniqueConstraint
from django.utils import timezone

from apps.core.models import Base, CreatedByMixin
from apps.permission.managers import PermissionManager


class Permission(CreatedByMixin, Base):
    objects = PermissionManager()

    class Meta:
        indexes = [models.Index(fields=['object_identifier'])]
        # do not include group_id here as it can be null and null != null for unique contraint in pg
        constraints = [UniqueConstraint(fields=['action', 'permission', 'user_id', 'object_identifier'],
                                       name='unique_permission')]

    class Action(models.TextChoices):
        # TODO expand that list
        VIEW = 'view'
        DOWNLOAD = 'download'
        SHARE = 'share'
        TRANSFER = 'transfer'

    class Permission(models.TextChoices):
        DENY = 'deny'
        ALLOW = 'allow'

    group = models.ForeignKey('user_group.Group', on_delete=models.SET_NULL, null=True, default=None,
                              related_name='permissions')
    # the node that this permissions belongs to
    user = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE, related_name='permissions')
    object_identifier = models.CharField(max_length=500)
    action = models.CharField(choices=Action.choices, max_length=20, null=False, blank=False)
    permission = models.CharField(choices=Permission.choices, max_length=10, null=False, blank=False)

    def __str__(self):
        return f'{self.user} {self.permission} {self.action} {self.object_identifier}'

    @staticmethod
    def create_permissions(*, identifiers: List[str], permission: Permission, action: Action,
                           user_id: str, created_by_id: str | None, group_id: str | None = None):
        with io.StringIO() as buffer:
            writer = csv.writer(buffer)
            csv_header = ['date_created', 'last_modified', 'id',
                          'object_identifier', 'permission', 'action',
                          'group_id', 'user_id', 'created_by_id']
            writer.writerow(csv_header)
            now = timezone.now().isoformat()
            group_id = 'null' if group_id is None else group_id
            writer.writerows([now, now, str(uuid.uuid4()), i, permission, action, group_id,
                              user_id, created_by_id] for i in identifiers)

            # the strategy is to ensure no duplicated permissions is:
            # insert into temp table first, then do an upsert into the permission table and do nothing on conflict (ignore duplicates).
            with connection.cursor() as cursor:
                buffer.seek(0)
                tmp_tbl_name = ''.join(random.choice(string.ascii_uppercase) for _ in range(5))
                # create tmp table from permission_permission with 1 record and truncate afterward
                # so the table structure is equal to the permission table, but it's truncated
                tbl_name = Permission.objects.model._meta.db_table
                cursor.execute(f'create temp table {tmp_tbl_name} as select * from {tbl_name} limit 1')
                cursor.execute(f'truncate table {tmp_tbl_name}')
                cursor.copy_expert(f'copy {tmp_tbl_name}({",".join(csv_header)}) from stdin csv header NULL as \'null\'',
                                   buffer)
                # insert into and on conflict do nothing
                cursor.execute(f'insert into {tbl_name} select * from {tmp_tbl_name} on conflict do nothing')
                cursor.execute(f'drop table {tmp_tbl_name}')

