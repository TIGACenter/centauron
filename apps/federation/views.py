import logging
from typing import Any

from constance import config
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, FormView

from apps.federation.forms import AddNodeForm
from apps.federation.messages import Message, UserMessage
from apps.node.models import Node
from apps.share.share_token import token_utils

User = get_user_model()


class MyCodeView(LoginRequiredMixin, TemplateView):
    template_name = 'federation/index.html'

    def get_context_data(self, **kwargs):
        return {
            'identifier': settings.IDENTIFIER,
            'certificate_thumbprint': config.CERTIFICATE_THUMBPRINT,
            'did': settings.ORGANIZATION_DID,
            'centauron_server': settings.ADDRESS,
            'node_name': settings.NODE_NAME,
            'common_name': settings.COMMON_NAME,
            'cdn_address': settings.CDN_ADDRESS
        }

    def post(self, request):
        # TODO get node here and create the code for the node.
        user = self.request.user.profile
        ctx = {}
        try:
            token = user.as_token()
            ctx = dict(token=token)
        except Exception as e:
            messages.error(request, str(e))
            logging.exception(e)

        return render(self.request, 'federation/partials/my-code.html', ctx)


class NodeListView(LoginRequiredMixin, TemplateView):
    template_name = 'federation/nodes-list.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        nodes = Node.objects.all()  # all_but_me()
        ctx.update({
            'nodes': nodes
        })
        return ctx


class AddNodeView(LoginRequiredMixin, FormView):
    form_class = AddNodeForm

    def form_valid(self, form):
        code = form.cleaned_data.get('code')
        token: Message = token_utils.parse_token(code)
        try:
            self.import_message(token)
            messages.success(self.request, 'Node imported.')
        # except exceptions.UserAlreadyExistsException as e:
        #     messages.error(self.request, str(e))
        except Exception as e:
            messages.error(self.request, str(e))
        return redirect('federation:index')

    def import_message(self, message: Message):
        if isinstance(message, UserMessage):
            Node.import_node(self.request.user.profile, message)


class DeleteNodeView(LoginRequiredMixin, View):

    def post(self, request, pk, *args, **kwargs):
        node = get_object_or_404(Node, pk=pk)
        node.delete_node()
        messages.warning(request, 'Not yet implemented.')
        return redirect('federation:node-list')
