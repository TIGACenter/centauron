from django.contrib import admin

from apps.node.models import Node


class NodeAdmin(admin.ModelAdmin):
    list_display = ('pk', 'human_readable', 'identifier', 'address_centauron', 'address_fhir_server')


admin.site.register(Node, NodeAdmin)
