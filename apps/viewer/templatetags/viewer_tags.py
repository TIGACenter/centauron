from uuid import UUID

from django import template
from django.conf import settings
from django.template.smartif import prefix
from django.urls import reverse

register = template.Library()


@register.simple_tag
def viewer_url(file, viewer=None):
    if not file.imported:
        return '#'

    if viewer is None:
        viewer = settings.VIEWER_MAPPINGS.get(file.content_type)
    if viewer is None:
        return reverse('viewer:select', kwargs=dict(pk=file.id_as_str))

    viewer_label = settings.VIEWER_APP_MAPPING.get(viewer)
    return reverse(viewer_label, kwargs=dict(pk=file.id_as_str))


@register.inclusion_tag("viewer/templatetags/file_link.html")
def viewer_link_file(file, viewer=None):
    url = viewer_url(file, viewer)
    return dict(url=url, file=file)
    # a = f'<a href="{url}">{file.name}</a>'
    # if file.imported:
    #     return f'<strong>{a}</strong>'
    # else:
    #     return a

@register.filter
def file_id_to_html_id(file_id):
    prefix = 'a'
    if isinstance(file_id, UUID):
        return prefix + file_id.hex
    return prefix + str(file_id).replace('-', '')

