from django import template
from django.utils import timezone

from apps.share.share_token.models import ShareToken

register = template.Library()

@register.filter
def is_valid(token: ShareToken):
    now = timezone.now()
    return token.valid_from <= now <= token.valid_until
