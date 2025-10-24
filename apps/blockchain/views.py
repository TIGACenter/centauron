from distutils.util import strtobool

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView

from apps.blockchain.models import Log


class ExplorerView(ListView):
    template_name = 'blockchain/explorer.html'
    paginate_by = 50
    model = Log
    ordering = ['-date_created']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            only_me = self.request.GET.get('only-me', 'false')
            if bool(strtobool(only_me)):
                qs = qs.filter(actor=self.request.user.profile)
        return qs

class NetworkView(LoginRequiredMixin, TemplateView):
    template_name = 'blockchain/network.html'
