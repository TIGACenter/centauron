from django import template
from django.conf import settings
from django.template import Template, Context

from apps.event.models import Event

register = template.Library()


@register.inclusion_tag("events/tags/render_event.html", takes_context=True)
def render_event(context, evt:Event):
    current_user = context.request.user.profile
    v = map_verb(evt).replace('{{s}}', '{{s|safe}}').replace('{{o}}', '{{o|safe}}')
    ctx = {'s': f'<strong>{get_subject(current_user, evt)}</strong>', 'o': f'<strong>{get_object(evt)}</strong>'}
    t = Template(v)
    st = t.render(Context(ctx))

    ctx = {
        'st': st,
        'event': evt
    }
    return ctx


def get_subject(current_user, evt:Event):
    if evt.subject.identifier == current_user.identifier:
        return 'You'
    return evt.subject.human_readable

def get_object(e:Event):
    if e.object_node is None:
        return 'unknown'
    if e.object_node.identifier == settings.IDENTIFIER:
        return 'you'
    return e.object_node.human_readable



def map_verb(evt:Event):
    '''
    {{s}} as a placeholder for subject.
    {{o}} as a placeholder for object.
    :param evt:
    :return:
    '''
    verb = evt.verb
    if verb == Event.Verb.PROJECT_CREATE:
        return '{{s}} created this project.'
    if verb == Event.Verb.PROJECT_MEMBER_INVITE:
        return '{{s}} invited {{o}} to collaborate on the project.'
    if verb == Event.Verb.PROJECT_MEMBER_REMOVED:
        return '{{s}} removed {{o}} from the project.'
    if verb == Event.Verb.SHARE_RECEIVE:
        return '{{s}} shared data with {{o}}.'
    if verb == Event.Verb.PROJECT_MEMBER_INVITE_ACCEPTED:
        return '{{s}} accepted the invitation.'
    if verb == Event.Verb.PROJECT_MEMBER_INVITE_DECLINED:
        return '{{s}} declined the invitation.'

    return 'unknown'
