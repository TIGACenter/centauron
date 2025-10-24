from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from apps.share.share_token.models import ShareToken


class CreateView(LoginRequiredMixin, TemplateView):
    template_name = 'share/share_token/create-dialog.html'

class ShareTokenActionView(LoginRequiredMixin, View):

    def post(self, request, pk, **kwargs):
        action_is_send = 'send' in request.POST
        action_is_delete = 'delete' in request.POST
        st = ShareToken.objects.get(pk=pk)
        if action_is_send:
            st.send_to_node()
            messages.success(request, f'Send to {st.recipient.human_readable}.')
        if action_is_delete:
            # TODO start some processes e.g. to delete some files from st.recipient?
            st.delete()
            messages.success(request, 'ShareToken deleted.')
        return redirect(request.META['HTTP_REFERER'])

