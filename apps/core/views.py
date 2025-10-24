from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View


class IndexView(View):
    # template_name = 'core/index.html'
    def get(self, request, **kwargs):
        return redirect('study_management:list')


class BaseTableActionView(LoginRequiredMixin, View):

    def get_queryset(self):
        model = getattr(self, 'model')
        if model is not None:
            # TODO do some input validation that self.rows only contains valid uuidv4s
            return model.objects.filter(pk__in=self.rows)

    def get_success_url(self):
        return getattr(self, 'success_url')

    def post(self, request, **kwargs):
        self.request = request
        self.rows = request.POST.getlist('rows')
        self.action()
        return redirect(self.get_success_url())

    def action(self, **kwargs):
        raise NotImplementedError()
