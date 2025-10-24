import uuid
from typing import Literal

from django.conf import settings

IDENTIFIER_FORMAT = '{}#{}'


def create_random(
    type: Literal['project'] | Literal['user'] | Literal['case'] | Literal['codesystem'] | Literal['file'] | Literal['dataset'] | Literal[
        'share'] | Literal[
              'share_token'] | Literal['evaluation-code'] | Literal['submission'] | Literal['computing-job-definition'] | Literal[
              'computing-job-execution'] | Literal['computing-job'] | Literal['computing-pipeline'] |
          Literal['computing-job-template'] | Literal['fileset'] | Literal['tileset'] | Literal['extra-data'] | Literal['ground-truth']| Literal['ground-truth-schema'] | Literal['submission-part']):
    system = settings.IDENTIFIER
    value = f'{type}::{uuid.uuid4()}'
    return f'{system}#{value}'


def from_string(s: str):
    '''
    :param s: string rep of an identifier: system#val
    :return:
    '''
    if s is None:
        return None
    if not isinstance(s, str):
        return None
    if not "#" in s:
        return s
    a = s.split('#')
    if len(a) != 2:
        return None

    return IDENTIFIER_FORMAT.format(a[0].strip(), a[1].strip())


def from_common_name(s: str) -> str:
    s = s.split('.')
    value = f'{s[1]}::{s[0]}'
    system = '.'.join(s[2:])
    return IDENTIFIER_FORMAT.format(system, value)


def create_identifier(val: str) -> str:
    return IDENTIFIER_FORMAT.format(settings.IDENTIFIER, val)
