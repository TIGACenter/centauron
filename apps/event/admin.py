from django.contrib import admin

from apps.event.models import Event


class EventAdmin(admin.ModelAdmin):
    list_display = ('pk', 'subject', 'verb', 'object_project', 'context_project', 'date_created')
    ordering = ('-date_created',)

admin.site.register(Event, EventAdmin)
