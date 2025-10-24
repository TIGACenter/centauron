from django.contrib import admin

from apps.blockchain.models import Log, Block, LastSeenBlock


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('id', 'event_date', 'action', 'actor_display', 'actor_identifier')
    ordering = ('-event_date',)

@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'message_hash', 'cid', 'date_created', 'cid_downloaded')
    ordering = ('-date_created',)

@admin.register(LastSeenBlock)
class LastSeenBlockAdmin(admin.ModelAdmin):
    list_display = ('id', 'block')
    ordering = ('-date_created',)
