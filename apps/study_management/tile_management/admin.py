from django.contrib import admin

from apps.study_management.tile_management.models import TileSet


class TileSetAdmin(admin.ModelAdmin):
    ordering = ('-date_created',)
    list_display = ('pk', 'name', 'date_created', 'study_arm',)
    list_display_links = ('name','pk',)
    # exclude fields with a large number of objects
    exclude = ('source', 'computing_job','files',)

admin.site.register(TileSet, TileSetAdmin)
