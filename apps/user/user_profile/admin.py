from django.contrib import admin

from apps.user.user_profile.models import Profile


class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'identifier', 'human_readable', 'date_created')
    list_display_links = ('user','identifier',)
    ordering = ('-date_created',)

admin.site.register(Profile, ProfileAdmin)
