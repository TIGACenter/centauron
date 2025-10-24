import json
import logging
from typing import List

from apps.core import identifier
from apps.federation.messages import DeleteMessage, RetractShareMessage, RetractShareMessageContent
from apps.federation.outbox.models import OutboxMessage
from apps.permission.models import Permission
from apps.project.models import Project
from apps.project.project_case.models import Case
from apps.project.project_ground_truth.models import GroundTruth
from apps.share.api import ShareBuilder, CodesHandler
from apps.share.models import Share
from apps.share.share_token.models import ShareToken
from apps.storage.extra_data.models import ExtraData
from apps.storage.models import File
from apps.terminology.models import CodeSystem
from apps.user.user_profile.models import Profile
from config import celery_app


def translate_file_query(model, tree):
    tree = json.loads(tree)
    op_mapping = {
        'select_equals': '',
        'select_any_in': '__in',
        # ''
    }

    if model.lower() == 'file':
        model = File

    qs = model.objects

    properties = tree.get('properties', None)
    if properties is None:
        negated = False
    else:
        negated = properties.get('not', False)

    kwargs = {}
    for k, v in tree.items():
        if k.startswith('children'):
            for rule in tree.get(k, []):
                field = rule['properties']['field']
                operator = rule['properties']['operator']
                value = rule['properties']['value']
                kwargs[field + op_mapping[operator]] = value[0]

    if negated:
        qs = qs.exclude(**kwargs)
    else:
        qs = qs.filter(**kwargs)
    # model.objects.filter(filesets__in=)
    return qs.distinct()


@celery_app.task(soft_time_limit=60 * 60 * 24)
def create_share(
    model: str,
    project_identifier,
    valid_from,
    valid_until,
    created_by_pk,
    target_nodes_pk: List[str],
    query,
    percentage,
    allowed_actions=None,
    case_pks=None,
    project_pk=None,
    share_name=None,
    share_pk: str = None,
    term_pks=None,
    ground_truth_pk=None,
    file_pks=None,
    extra_data_applications=None,
    initial_file_list_id=None
):
    # TODO percentage is ignored for now.
    created_by = Profile.objects.get(pk=created_by_pk)
    if project_pk is None:
        project = Project.objects.filter_by_identifier(project_identifier).first()
    else:
        project = Project.objects.get(pk=project_pk)
    recipients = project.members.filter(user_id__in=target_nodes_pk)
    logging.info('Start to create share -> %s', recipients)
    if share_name is None or len(share_name.strip()) == 0:
        share_name = 'Share'
    if allowed_actions is None:
        allowed_actions = []
    if extra_data_applications is None:
        extra_data_applications = []
    if initial_file_list_id is None:
        initial_file_list_id = []

    model_is_file = model.lower() == 'file'
    file_qs = None
    codes = []
    codesystem_ids = []
    case_ids = []
    file_identifiers = []
    # calc_total = lambda qs: int(qs.count() * (percentage / 100))
    if case_pks is not None and len(case_pks) > 0:
        case_ids = case_pks
        # qs = Case.objects.filter(id__in=case_ids, projects__id=project.pk)
        file_qs = project.files_for_user(created_by).filter(case_id__in=case_ids)
        file_identifiers = file_qs.values_list('identifier', flat=True)
        # total = calc_total(qs)
        # term_ids = {t for t in qs.values_list('codes', flat=True) if t is not None}
        # file_identifiers = qs.values_list('files__identifier', flat=True)
        # only files that are in this project
        # file_identifiers = File.objects.filter(case__in=qs, projects__id=project.pk).values_list('identifier',
        #                                                                                          flat=True)
        # qs = qs[:total]
        # file_qs = File.objects.filter(projects__id=project.pk, id__in=qs.values_list('files__id', flat=True))
        # file_terms = {t for t in file_qs.values_list('codes', 'id') if t is not None}
        # term_ids = term_ids.union(file_terms)
        codes = file_qs.values_list('codes', 'id', named=True)
        codesystem_ids = file_qs.values_list('codes__codesystem_id', flat=True).distinct()
    # else:
    #     file_qs = translate_file_query(model, query)
    #     # calculate the relative number of files to be shared
    #     total = calc_total(file_qs)
    #     # TODO check if slicing after distinct returns always the correct result or also unwanted cases
    #     case_ids = file_qs.values_list('case_id', flat=True).distinct()
    #     file_identifiers = file_qs.values_list('identifier', flat=True)
    #     codes = file_qs.values_list('id', 'codes', named=True)
    #     codesystem_ids = file_qs.values_list('codes__codesystem_id', flat=True).distinct()

    if file_pks is not None and len(file_pks) > 0:
        file_qs = project.files_for_user(created_by).filter(id__in=file_pks)
        codes = file_qs.values_list('id', 'codes', named=True)
        codesystem_ids = file_qs.values_list('codes__codesystem_id', flat=True).distinct()
        file_identifiers = file_qs.values_list('identifier', flat=True)
        case_ids = file_qs.values_list('case_id', flat=True).distinct()

    # delete the terms that are selected
    # the file that have this term will still be included in this share
    terms_selected = [c for c in codes if str(c.codes) in term_pks]

    codesystem_qs = CodeSystem.objects.filter(id__in=codesystem_ids)
    case_qs = Case.objects.filter(id__in=case_ids)

    extra_data = project.extra_data_for_user(created_by).filter(application_identifier__in=extra_data_applications, file_id__in=initial_file_list_id)

    for n in recipients:
        for action in allowed_actions:
            Permission.create_permissions(identifiers=file_identifiers,
                                          permission=Permission.Permission.ALLOW,
                                          action=action,
                                          user_id=n.user.id_as_str,
                                          created_by_id=created_by_pk)
    builder = ShareBuilder(share_pk, share_name, created_by=created_by, origin=created_by, project=project,
                           file_query=query)
    builder.add_type_handler(data='data-release')
    if file_qs is not None:
        builder.add_file_handler(data=file_qs)
    builder.add_case_handler(data=case_qs)
    builder.add_codesystem_handler(data=codesystem_qs)
    builder.add_codes_handler(data=terms_selected, handler_init_kwargs={
        '__name__': CodesHandler.name_files if model_is_file else CodesHandler.name_cases})
    builder.add_permission_handler(data=','.join(list(map(lambda e: f'\'{e}\'', file_identifiers))))
    builder.add_extra_data_handler(data=extra_data)

    if ground_truth_pk is not None:
        builder.set_ground_truth(GroundTruth.objects.get(pk=ground_truth_pk))
    # FIXME TypeError: Cannot create distinct fields once a slice has been taken.
    share = builder.build(project_identifier)

    for n in recipients:
        ShareToken.objects.create(project_identifier=project_identifier,
                                  created_by_id=created_by_pk,
                                  share=share,
                                  identifier=identifier.create_random('share_token'),
                                  # created_by=created_by,
                                  recipient=n.user,
                                  valid_from=valid_from,
                                  valid_until=valid_until)

    logging.info('Done creating share.')

    send_share_to_sharetokens(share_pk)


@celery_app.task
def send_share_to_sharetokens(share_pk):
    logging.info('[start] send share to sharetoken.')
    tokens = ShareToken.objects.filter(share_id=share_pk)
    for t in tokens:
        t.send_to_node()
    logging.info('[end] send share to sharetoken.')


@celery_app.task(ignore_result=True)
def retract_share(share_pk):
    logging.info('[start] retract share.')
    share = Share.objects.get(pk=share_pk)

    for st in share.tokens.all():
        msg = OutboxMessage.create(
            sender=share.origin,
            recipient=st.recipient,
            message_type=DeleteMessage,
            message_object=RetractShareMessage(content=RetractShareMessageContent(identifier=share.identifier))
        )
        msg.send()

    logging.info('[end] retract share.')
