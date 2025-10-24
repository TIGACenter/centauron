from django.contrib import admin

from apps.challenge.challenge_client.models import ChallengeParticipants, ChallengeParticipantApproval


@admin.register(ChallengeParticipants)
class ChallengeParticipantsAdmin(admin.ModelAdmin):
    list_display = ('pk', 'challenge',)


@admin.register(ChallengeParticipantApproval)
class ChallengeParticipantApprovalAdmin(admin.ModelAdmin):
    list_display = ('pk', 'challenge', 'profile','approved')


    @admin.display(description="Challenge")
    def challenge(self, obj):
        return obj.challenge_participants.challenge.name  # Dynamically gets the challenge name
