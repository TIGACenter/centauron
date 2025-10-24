import logging
from typing import List

from celery import shared_task
from django.utils.text import slugify

from apps.challenge.models import Challenge
from apps.computing.models import ComputingPipeline
from apps.permission.models import Permission
from apps.project.project_case.models import Case
from apps.share.api import ShareBuilder, CodesHandler
from apps.share.share_token.models import ShareToken
from apps.terminology.models import CodeSystem
from apps.user.user_profile.models import Profile


@shared_task
def share_challenge(created_by_pk: str,
                    challenge_pk: str,
                    datasets: List[str],
                    recipient_pk: str):
    created_by = Profile.objects.get(pk=created_by_pk)
    recipient = Profile.objects.get(pk=recipient_pk)

    challenge = Challenge.objects.get(pk=challenge_pk)
    datasets = challenge.datasets.filter(id__in=datasets)
    files = None
    for d in datasets:
        if files is None:
            files = d.files.all()
        else:
            files = files.union(d.files.all())

    # files may be none if no dataset was selected
    if files is not None:
        cases = Case.objects.filter(id__in=files.values_list('case', flat=True))

    builder = ShareBuilder(name=challenge.name,
                           origin=created_by,
                           challenge=challenge,
                           created_by=created_by,
                           pk=None)

    # set permissions per default to only download
    Permission.objects.create_permissions(permission=Permission.Permission.ALLOW,
                                          actions=[Permission.Action.DOWNLOAD],
                                          created_by=created_by,
                                          users=[recipient],
                                          queryset=files)
    file_identifiers = files.values_list('identifier', flat=True)
    codes = files.values_list('id', 'codes', named=True)
    querysets = CodeSystem.objects.filter(id__in=files.values_list('codes__codesystem', flat=True))
    share = builder \
        .add_challenge_handler(dict(challenge=challenge, datasets=datasets.values_list('id', flat=True),
                                    target_metrics=challenge.target_metrics.values_list('id', flat=True))) \
        .add_codesystem_handler(querysets) \
        .add_codes_handler(codes, handler_init_kwargs={'__name__': CodesHandler.name_files}) \
        .add_case_handler(cases) \
        .add_file_handler(files) \
        .add_permission_handler(file_identifiers) \
        .build()

    # share is valid as long as the challenge is open
    valid_from = challenge.open_from
    valid_until = challenge.open_until
    st = ShareToken.create(
        share=share,
        created_by=created_by,
        valid_until=valid_until,
        valid_from=valid_from,
        recipient=recipient
    )

    st.send_to_node()

    logging.info('Share created.')


@shared_task
def create_pipeline_from_yml(challenge_pk, created_by_pk):
    challenge = Challenge.objects.get(pk=challenge_pk)
    origin = Profile.objects.get(pk=created_by_pk)
    k8s_namespace = slugify(challenge.name)
    k8s_namespace = k8s_namespace[:min(len(k8s_namespace), 63)]
    challenge.pipeline = ComputingPipeline.from_yml(origin, origin, challenge.pipeline_yml,
                                                    k8s_namespace)  # k8s namespace can only be max 63 characters
    challenge.save(update_fields=['pipeline'])
