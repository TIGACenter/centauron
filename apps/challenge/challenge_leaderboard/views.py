from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from apps.challenge.challenge_leaderboard.models import LeaderboardEntry
from apps.challenge.challenge_leaderboard.tasks import sent_leaderboard_to_hub
from apps.challenge.models import Challenge


class ListView(LoginRequiredMixin, TemplateView):
    template_name = 'challenge/challenge_leaderboard/list.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge = Challenge.objects.get(pk=self.kwargs.get('pk'))
        entries = LeaderboardEntry.objects.filter(challenge=challenge).order_by('position')
        target_metrics = challenge.target_metrics.all()
        sort_criterion = challenge.target_metrics.filter(sort__isnull=False).first()
        last_modified = entries.order_by('last_modified').first().last_modified if entries.count() > 0 else None

        ctx.update({
            'challenge': challenge,
            'entries': entries,
            'target_metrics': target_metrics,
            'sort_criterion': sort_criterion,
            'last_modified': last_modified,
        })
        return ctx


class CalculateLeaderboardView(LoginRequiredMixin, View):

    def post(self, request, pk):
        challenge = Challenge.objects.get(pk=pk)
        LeaderboardEntry.calculate_leaderboard(challenge)
        messages.success(request, 'Leaderboard calculated.')
        return redirect('challenge:challenge_leaderboard:list', pk=pk)


class SendLeaderboardView(LoginRequiredMixin, View):

    def post(self, request, pk):
        challenge = Challenge.objects.get(pk=pk)
        sent_leaderboard_to_hub(challenge.id_as_str, self.request.user.profile.id_as_str) # TODO .delay
        messages.success(request, 'Leaderboard is sent to Hub shortly.')
        return redirect('challenge:challenge_leaderboard:list', pk=pk)
