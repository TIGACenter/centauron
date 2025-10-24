from django.contrib import admin

from apps.challenge.models import Challenge

class ChallengeAdmin(admin.ModelAdmin):
    list_display = ('name', 'date_created')
    ordering = ('-date_created',)
    list_display_links = ('name',)
    exclude = ('tags', 'codes', 'annotations',)


admin.site.register(Challenge, ChallengeAdmin)
