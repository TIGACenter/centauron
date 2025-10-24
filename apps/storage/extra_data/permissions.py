from django.conf import settings
from rest_framework import permissions


class IsUserAnnotationBackend(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.user.username == settings.ANNOTATION_BACKEND_USERNAME
