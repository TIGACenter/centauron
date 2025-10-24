from django.contrib import admin

from apps.computing.models import ComputingJobDefinition, ComputingPipeline, ComputingJobTemplate

class ComputingJobDefinitionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'name', 'date_created', 'pipeline', 'identifier', )
    ordering = ('-date_created',)

admin.site.register(ComputingJobDefinition, ComputingJobDefinitionAdmin)

class ComputingPipelineAdmin(admin.ModelAdmin):
    list_display = ('pk','name', 'date_created', 'is_template', )
    ordering = ('-date_created',)

admin.site.register(ComputingPipeline, ComputingPipelineAdmin)


class ComputingJobTemplateAdmin(admin.ModelAdmin):
    list_display = ('pk', 'identifier', 'date_created')
    ordering = ('-date_created',)


admin.site.register(ComputingJobTemplate, ComputingJobTemplateAdmin)
