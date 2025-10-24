import json

import humanize
import markdown
from django import template
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.encoding import escape_uri_path

register = template.Library()


# https://github.com/valerymelou/django-active-link/blob/master/active_link/templatetags/active_link_tags.py
@register.simple_tag(takes_context=True)
def active_link_app(context, app_names, css_class='active', *args, **kwargs):
    request = context.get('request')
    if request is None:
        # Can't work without the request object.
        return ''
    if request.resolver_match.app_name in app_names.split(' '):
        return css_class
    return ''


@register.filter
def duration(start, end):
    if start is not None:
        if end is None: end = timezone.now()
        delta = end - start
        return humanize.precisedelta(delta, format='%0.0f')
    return ''


@register.simple_tag(takes_context=True)
def active_link(context, viewnames=None, css_class='active', inactive_class='', namespace=None, strict=None, *args,
                **kwargs):
    """
    Renders the given CSS class if the request path matches the path of the view.
    :param context: The context where the tag was called. Used to access the request object.
    :param viewnames: The name of the view or views separated by || (include namespaces if any).
    :param css_class: The CSS class to render.
    :param inactive_class: The CSS class to render if the views is not active.
    :param strict: If True, the tag will perform an exact match with the request path.
    :return:
    """
    # if css_class is None:
    #     css_class = getattr(settings, 'ACTIVE_LINK_CSS_CLASS', 'active')
    #
    # if strict is None:
    #     strict = getattr(settings, 'ACTIVE_LINK_STRICT', False)
    # css_class = 'active'
    strict = True
    request = context.get('request')
    if request is None:
        # Can't work without the request object.
        return ''

    if namespace is not None:
        if context.request.resolver_match.app_name in namespace:
            return css_class

    active = False
    if viewnames is not None:
        views = viewnames.split(' ')
        for viewname in views:
            try:
                path = reverse(viewname.strip(), args=args, kwargs=kwargs)
            except NoReverseMatch:
                continue
            request_path = escape_uri_path(request.path)
            if strict:
                active = request_path == path
            else:
                active = request_path.find(path) == 0
            if active:
                break

    if active:
        return css_class

    if viewnames is not None:
        # TODO does not take parameters into account
        if request.resolver_match.view_name == views[0]:
            return css_class

    return inactive_class


@register.simple_tag
def settings(name):
    from django.conf import settings
    return getattr(settings, name, "")


@register.filter
def markdownify(value):
    if value is None: return ''
    return markdown.markdown(value)


@register.simple_tag
def call_method(obj, method_name, *args):
    method = getattr(obj, method_name)
    return method(*args)

@register.simple_tag
def to_json(obj):
    return json.dumps(obj)

@register.filter
def for_origin(qs, origin):
    return qs.filter(origin=origin)

@register.filter
def for_created_by(qs, origin):
    return qs.filter(created_by=origin)
