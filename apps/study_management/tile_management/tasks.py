import csv
import logging
import shutil
from collections import deque

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from apps.core import identifier
from apps.federation.messages import ShareObject
from apps.federation.outbox.models import OutboxMessage
from apps.permission.models import Permission
from apps.share.api import ShareBuilder, CodesHandler
from apps.share.share_token.models import ShareToken
from apps.study_management.import_data.models import ImportJob
from apps.study_management.import_data.tasks import run_importer_tileset
from apps.study_management.tile_management.models import TileSet
from apps.user.user_profile.models import Profile


@shared_task(soft_time_limit=60 * 60 * 24)
def export_tileset_as_csv(tileset_pk, columns):
    tileset = TileSet.objects.get(pk=tileset_pk)
    filename = f'{slugify(tileset.name)}-{timezone.now().isoformat()}.csv'
    path = settings.STORAGE_EXPORT_DIR / (filename + '.exporting')
    with path.open('w') as f:
        deque(export_tileset_as_csv_writer(columns, tileset, f), maxlen=0)

    shutil.move(path, settings.STORAGE_EXPORT_DIR / filename)


def export_tileset_as_csv_writer(columns, tileset, buffer):
    # ['name', 'identifier', 'path', 'case', 'content_type', 'size',
    #                                         'concepts', 'src']
    writer = csv.DictWriter(buffer, fieldnames=columns)
    yield writer.writeheader()
    qs = tileset.files.all()
    if 'case' in columns:
        qs = qs.prefetch_related('case')
    if 'src' in columns:
        qs = qs.prefetch_related('originating_from')
    if 'codes' in columns:
        qs = qs.prefetch_related('codes')
    if 'metadata' in columns:
        qs = qs.prefetch_related('annotations')

    def write_columns(d, colum, val):
        if colum in columns:
            d[colum] = val

    for file in qs:
        d = dict()
        write_columns(d, 'name', file.name)
        write_columns(d, 'identifier', file.identifier)
        write_columns(d, 'path', file.path)
        write_columns(d, 'content_type', file.content_type)
        write_columns(d, 'size', file.size)
        if 'case' in columns:
            case = file.case.name if file.case else None
            write_columns(d, 'case', case)
        if 'src' in columns:
            src = file.originating_from.identifier if file.originating_from else None
            write_columns(d, 'src', src)
        if 'codes' in columns:
            write_columns(d, 'codes', ','.join(file.code_list_identifier_rep()))
        if 'metadata' in columns:
            write_columns(d, 'metadata', ','.join([f'{a.system}={a.value}' for a in file.annotations.all()]))

        yield writer.writerow(d)


@shared_task(soft_time_limit=60 * 60 * 24)
def update_tileset(tileset_pk: str, csv_path: str):
    tileset = TileSet.objects.get(pk=tileset_pk)
    tileset.files.clear()
    # TODO set some status or so to notify the user
    job = ImportJob.objects.create(
        created_by=tileset.created_by,
        study_arm_id=tileset.study_arm_id,
        file=csv_path)
    run_importer_tileset.delay(job.id_as_str, tileset.id_as_str)  # .TODO delay


@shared_task(soft_time_limit=60 * 60 * 24)
def copy_tileset(src_pk: str, dst_pk: str):
    src = TileSet.objects.get(pk=src_pk)
    dst = TileSet.objects.get(pk=dst_pk)
    dst.set_status(TileSet.Status.COPYING)
    logging.info('Copy tileset %s to %s', src.name, dst.name)
    dst.terms.set(src.terms.all())
    dst.files.set(src.files.all())
    dst.set_status(TileSet.Status.IDLE)
    logging.info('Copy tileset done.')


@shared_task(soft_time_limit=60 * 60 * 24)
def create_tileset_share(tileset_pk, project_identifier, valid_from, valid_until, created_by_pk, target_node_pk,
                         file_query):
    tileset = TileSet.objects.get(pk=tileset_pk)
    created_by = Profile.objects.get(pk=created_by_pk)
    logging.info('Start to create share for tileset %s -> %s', tileset, target_node_pk)
    file_identifiers = tileset.files.values_list('identifier', flat=True)
    Permission.create_permissions(identifiers=file_identifiers,
                                  permission=Permission.Permission.ALLOW,
                                  action=Permission.Action.TRANSFER,
                                  user_id=target_node_pk,
                                  created_by_id=created_by_pk)
    file_concepts = tileset.files.values_list('id', 'codes', named=True)
    builder = ShareBuilder(f'Share for {tileset.name}', created_by=created_by)
    files_qs = tileset.files.all()
    case_ids = tileset.files.values_list('case_id', flat=True).distinct()
    builder.add_file_handler(data=files_qs)
    builder.add_case_handler(data=case_ids)
    builder.add_codes_handler(data=file_concepts, handler_init_kwargs={'__name__': CodesHandler.name_files})
    builder.add_permission_handler(data=','.join(list(map(lambda e: f'\'{e}\'', file_identifiers))))
    share = builder.build(project_identifier)

    ShareToken.objects.create(project_identifier=project_identifier,
                              share=share,
                              identifier=identifier.create_random('share_token'),
                              created_by=created_by,
                              recipient_id=target_node_pk,
                              valid_from=valid_from,
                              valid_until=valid_until)

    logging.info('Done creating tileset share.')

    recipient = Profile.objects.get(pk=target_node_pk)
    object = ShareObject(content=share.content)
    OutboxMessage.create(
        sender=created_by,
        recipient=recipient,
        message_object=object,
    ).send()
