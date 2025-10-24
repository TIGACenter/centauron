from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.views import View
from django.views.generic import FormView, TemplateView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.terminology.forms import DialogAddForm
from apps.terminology.models import Code


class TerminologyDialogAddView(LoginRequiredMixin, FormView):
    template_name = 'terminology/dialog-add.html'
    form_class = DialogAddForm

    def get_action_url(self):
        raise NotImplementedError()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = self.get_action_url()
        return ctx


class CodeSearch(APIView):
    permission_classes = [IsAuthenticated, ]

    def get(self, request, **kwargs):
        qs = Code.objects.filter(Q(created_by__isnull=True) | Q(created_by=request.user.profile))
        q = request.GET.get('q')
        if q:
            qs = qs.filter(Q(code__icontains=q) | Q(human_readable__icontains=q))
        # TODO if this is to slow then use a elastic search index but first try an index on (created_by, code)
        limit = 100
        total = qs.count()
        data = [dict(id=c.id_as_str, code=c.code, human_readable=c.human_readable, codesystem=c.codesystem_name) for c in qs[:min(limit, total)]]
        # if limit < total:


        return JsonResponse(data=data, safe=False)
