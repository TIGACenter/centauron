from django import template

from apps.share.models import Share
from apps.share.share_token.models import ShareToken

register = template.Library()

@register.filter
def shared_with_list(share:Share):
    return ', '.join(share.tokens.values_list('recipient__human_readable', flat=True))

