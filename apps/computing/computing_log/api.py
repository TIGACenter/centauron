import logging

from django.http import HttpResponse

from apps.computing.computing_executions.api import BaseAPIView
from apps.computing.computing_log.tasks import persist_log


class LogView(BaseAPIView):

    def post(self, request, pk):
        logging.debug('Adding new log from stage.')
        data = request.data
        log = data['line']
        position = data['position']
        type = data.get('type', 'output')

        # save in celery
        persist_log.delay(pk, log, position, type)

        return HttpResponse(status=200)

