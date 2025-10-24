from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404
from django.views import View

from apps.computing.computing_artifact.models import ComputingJobArtifact


class DownloadView(LoginRequiredMixin, View):

    def get(self, request, challenge_pk, submission_pk, artefact_pk):
        artefact = ComputingJobArtifact.objects.get(pk=artefact_pk) # TODO computing_job__definition__pipeline__challenge_id=challenge_pk, computing_job__definition__pipeline__submission_id=submission_pk
        if not artefact.file.imported:
            raise Http404()
        path = settings.STORAGE_DATA_DIR / artefact.file.path
        if not path.exists():
            raise Http404()

        response = FileResponse(
            path.open('rb'),
            filename=artefact.file.name,
            as_attachment=True
        )
        response['X-Filename'] = artefact.file.name # TODO quoting the value necessary here??
        return response
