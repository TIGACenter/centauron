from itertools import product
from typing import Any, Dict

from django.db import models
from django.db.models import QuerySet

from apps.node.models import Node
from apps.project.project_case.models import Case
from apps.storage.models import File


class PermissionManager(models.Manager):

    def has_permissions(self, user, object_identifier, action):
        qs = self.filter(object_identifier=object_identifier, action=action, user=user)
        if qs.exists():
            return qs.first().permission

        # default is deny
        from apps.permission.models import Permission
        return Permission.Permission.DENY

    def create_permissions(self, *, permission, queryset: QuerySet | Dict[str, Any], created_by, actions, users: QuerySet[Node]):
        '''

        :param permission:
        :param queryset: if a dict, the form should be: {'48632643-ea96-4084-823e-9aa086a61617': {'actions': ['download', 'transfer'], 'files': {'bebdd583-f9d4-4f65-87af-479a676bc702': ['view', 'share']}}}

        :param created_by:
        :param actions:
        :param user:
        :return:
        '''
        from apps.permission.models import Permission
        # TODO this gives all items in queryset the same permissions for the same actions
        # TODO do some more detailed differentiation here
        # TODO use custom import via csv into postgres table for speeeed
        # input should be more like a matrix: columns are permissions and rows are the entities of the queryset. the values in the cells are ALLOW or DENY.
        if isinstance(queryset, QuerySet):
            for e, action in product(queryset.all(), actions):
                for n in users:
                    i, _ = self.get_or_create(action=Permission.Action[action.upper()],
                                permission=Permission.Permission[permission.upper()],
                                object_identifier=e.identifier,
                                user=n)
                    i.created_by = created_by
                    i.save()
        if isinstance(queryset, Dict):
            for case in queryset:
                case_ = queryset[case]
                case_actions = case_['actions']
                for action in case_actions:
                    for n in users:
                        i, _ = self.get_or_create(action=Permission.Action[action.upper()],
                                    permission=Permission.Permission.ALLOW,
                                    object_identifier=Case.objects.get(pk=case).identifier,
                                    user=n)
                        i.created_by = created_by
                        i.save()
                for file in case_['files']:
                    file_actions = case_['files'][file]
                    for action in file_actions:
                        for n in users:
                            i, _ = self.create(action=Permission.Action[action.upper()],
                                        permission=Permission.Permission.ALLOW,
                                        object_identifier=File.objects.get(pk=file, case_id=case).identifier,
                                        user=n)
                            i.created_by = created_by
                            i.save()
