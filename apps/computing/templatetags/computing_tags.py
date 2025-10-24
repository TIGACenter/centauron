from django import template

register = template.Library()

@register.filter()
def pipeline_was_executed(pipeline, user):
    return pipeline.was_executed(user)
