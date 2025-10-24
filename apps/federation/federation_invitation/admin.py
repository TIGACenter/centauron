from django.contrib import admin

from apps.federation.federation_invitation.models import FederationInvitation


class FederationInvitationAdmin(admin.ModelAdmin):
    list_display = ('pk', 'to', 'status', 'date_created')
    ordering = ['-date_created']

admin.site.register(FederationInvitation, FederationInvitationAdmin)
