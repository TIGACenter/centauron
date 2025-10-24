from functools import partial

from django.contrib import admin
from django.db import transaction
from django.shortcuts import redirect
from django.urls import path

from apps.federation.outbox.models import OutboxMessage
from apps.federation.outbox.tasks import send_outbox_message


class OutboxMessageAdmin(admin.ModelAdmin):
    list_display = ('pk', 'date_created', 'recipient', 'sender', 'processing', 'processed', 'tries')
    ordering = ('-date_created',)
    change_form_template = 'admin/federation/outbox/change_form.html'

    def replay(self, request, object_id):
        obj = self.get_object(request, object_id)

        obj.processed = False
        obj.processing = False
        obj.save()

        transaction.on_commit(partial(send_outbox_message.delay, obj.id_as_str))

        self.message_user(request, "Replaying inbox message!")
        return redirect('admin:outbox_outboxmessage_change', object_id)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/replay/', self.admin_site.admin_view(self.replay),
                 name='outbox_outboxmessage_replay'),
        ]
        return custom_urls + urls


admin.site.register(OutboxMessage, OutboxMessageAdmin)
