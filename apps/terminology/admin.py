from django.contrib import admin

from apps.terminology.models import Code, CodeSystem, CodeSet


class CodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'codesystem_name', 'human_readable', 'date_created')
    list_display_links = ('code',)
    ordering = ('-date_created',)


admin.site.register(Code, CodeAdmin)


class CodeSystemAdmin(admin.ModelAdmin):
    list_display = ('pk', 'name', 'uri', 'date_created')
    ordering = ('-date_created',)
    list_display_links = ('pk', 'name',)


admin.site.register(CodeSystem, CodeSystemAdmin)


class CodeSetAdmin(admin.ModelAdmin):
    list_display = ('pk', 'get_project', 'date_created',)
    ordering = ('-date_created',)

    @admin.display
    def get_project(self, o: CodeSet):
        return o.project.name if o.project is not None else ''


admin.site.register(CodeSet, CodeSetAdmin)
