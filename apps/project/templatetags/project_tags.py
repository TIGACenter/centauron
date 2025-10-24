import logging

from django import template

from apps.node.models import Node
from apps.project.models import Project
from apps.terminology.models import Code
from apps.user.user_profile.models import Profile

register = template.Library()


@register.simple_tag(takes_context=True)
def active_view(context, val):
    view_name = context.request.resolver_match.view_name
    if view_name != 'project:detail-view':
        return ''
    is_view = context.request.resolver_match.kwargs['view_pk'] == val
    return 'active' if is_view else ''


@register.simple_tag
def number_of_cases(project: Project, user: Profile):
    return project.cases.filter(origin=user).count()


@register.simple_tag
def number_of_files(project: Project, user: Profile):
    return project.files.filter(origin=user).count()

@register.simple_tag
def number_of_files_downloaded(project: Project, user: Profile):
    return project.files.filter(origin=user, imported=True).count()

@register.simple_tag
def files_with_code(project: Project, code: Code):
    return code.file_codes.filter(projects=project).count()

@register.simple_tag
def cases_with_code(project: Project, code: Code):
    return code.file_codes.filter(projects=project).values_list('case_id', flat=True).distinct().count()

@register.filter
def user_is_project_owner(project, user):
    return project.user_is_owner(user)

@register.filter
def project_name_from_message(message):
    content = message.get('object').get('content')
    # content = message.get('content', [])
    # print(message)
    for c in content:
        if c.get('type') == 'project':
            return c.get('name')
    logging.info(message)
    return 'project name not found.'
