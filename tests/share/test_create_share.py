import json
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.node.models import Node
from apps.permission.models import Permission
from apps.project.project_case.models import Case
from apps.share import tasks
from apps.share.models import Share
from apps.share.share_token.models import ShareToken
from apps.storage.fileset.models import FileSet
from apps.storage.models import File
from apps.terminology.models import Code, CodeSystem


class TestCreateShare:

    @pytest.mark.django_db
    def test_create_share(self, setup, user, project):
        # TODO add codes to test
        recipient = Node.objects.create()
        r2 = Node.objects.create()
        file_query = '{}'
        allowed_actions = [Permission.Action.DOWNLOAD, Permission.Action.VIEW]
        codesystem = CodeSystem.objects.create(project=project, name=uuid.uuid4().hex, uri=uuid.uuid4().hex)
        code = Code.objects.create(codesystem=codesystem, code=uuid.uuid4().hex, origin=project.origin)

        n = 10
        m = 5
        for i in range(n):
            c = Case.objects.create(
                identifier=uuid.uuid4().hex,
                name=uuid.uuid4().hex,
            )
            c.projects.add(project)
            for j in range(m):
                f = File.objects.create(
                    case=c,
                    identifier=uuid.uuid4().hex,
                    name=uuid.uuid4().hex,
                    original_filename=uuid.uuid4().hex,
                    original_path=uuid.uuid4().hex,
                    size=10
                )
                f.codes.add(code)

        case_pks = list(Case.objects.values_list('id', flat=True))
        file_pks = list(File.objects.values_list('id', flat=True))
        valid_from = timezone.now()
        valid_until = timezone.now() + timedelta(days=1)
        tasks.create_share(
            model='file',
            project_identifier=project.identifier,
            valid_from=valid_from,
            valid_until=valid_until,
            created_by_pk=user.id_as_str,
            target_nodes_pk=[recipient.id_as_str, r2.id_as_str],
            query=file_query,
            case_pks=case_pks,
            allowed_actions=allowed_actions,
            percentage=0)

        s = Share.objects.first()

        assert s.cases.count() == n
        assert s.files.count() == n * m
        assert s.codes.count() == 1
        assert Permission.objects.count() == n * m * 2 * len(allowed_actions)  # x2 for two receiving nodes
        assert ShareToken.objects.count() == 2
        assert ShareToken.objects.filter(recipient=recipient, project_identifier=project.identifier,
                                         valid_from=valid_from, valid_until=valid_until).exists()
        assert ShareToken.objects.filter(recipient=r2, project_identifier=project.identifier, valid_from=valid_from,
                                         valid_until=valid_until).exists()
        Share.objects.filter().delete()
        Permission.objects.filter().delete()

        tasks.create_share(
            model='file',
            project_identifier=project.identifier,
            valid_from=valid_from,
            valid_until=valid_until,
            created_by_pk=user.id_as_str,
            target_nodes_pk=[recipient.id_as_str, r2.id_as_str],
            query=file_query,
            file_pks=file_pks,
            allowed_actions=allowed_actions,
            percentage=0)

        s = Share.objects.first()

        assert s.cases.count() == n
        assert s.files.count() == n * m
        assert s.codes.count() == 1
        assert Permission.objects.count() == n * m * 2 * len(allowed_actions)  # x2 for two receiving nodes
        assert ShareToken.objects.count() == 2
        assert ShareToken.objects.filter(recipient=recipient, project_identifier=project.identifier,
                                         valid_from=valid_from, valid_until=valid_until).exists()
        assert ShareToken.objects.filter(recipient=r2, project_identifier=project.identifier, valid_from=valid_from,
                                         valid_until=valid_until).exists()

    @pytest.mark.django_db
    def test_translate_file_query_two_concepts(self, user, project):
        concept_1 = 'concept_1'
        concept_2 = 'concept_2'
        cs = CodeSystem.objects.create(name='abc', uri='abc')
        concept_1 = Code.objects.create(code=concept_1, codesystem=cs)
        concept_2 = Code.objects.create(code=concept_2, codesystem=cs)

        n_files = 100
        for i in range(n_files):
            f = File.objects.create(created_by=user, name=str(uuid.uuid4()))
            if i < n_files / 2:
                f.codes.add(concept_1)
            else:
                f.codes.add(concept_2)

        tree = lambda concept_id, negated=False: {
            "id": "a8889b8b-0123-4456-b89a-b189883fe954",
            "type": "group",
            "children1": [
                {
                    "type": "rule",
                    "id": "999ba8ab-0123-4456-b89a-b189883ff396",
                    "properties": {
                        "field": "codes",
                        "operator": "select_equals",
                        "value": [concept_id],
                        "valueSrc": [
                            "value"
                        ],
                        "valueType": [
                            "select"
                        ]
                    }
                }
            ],
            "properties": {
                "not": negated
            }
        }
        qs = tasks.translate_file_query('file', json.dumps(tree(concept_1.id_as_str)))

        assert n_files / 2 == qs.count()
        for f in qs:
            assert f.codes.count() == 1
            assert f.codes.first().code == concept_1.code

        qs = tasks.translate_file_query('file', json.dumps(tree(concept_2.id_as_str)))

        assert n_files / 2 == qs.count()
        for f in qs:
            assert f.codes.count() == 1
            assert f.codes.first().code == concept_2.code

        # qs = tasks.translate_file_query('file', json.dumps(tree(concept_2.id_as_str, negated=True)))
        #
        # assert n_files / 2 == qs.count()
        # for f in qs:
        #     assert f.concepts.count() == 1
        #     assert f.concepts.first().concept == concept_2.concept

    @pytest.mark.django_db
    def test_translate_file_query_two_concepts_negated(self, user, project):
        concept_1 = 'concept_1'
        cs = CodeSystem.objects.create(name='abc', uri='abc')
        concept_1 = Code.objects.create(code=concept_1, codesystem=cs)

        n_files = 100
        for i in range(n_files):
            f = File.objects.create(created_by=user, name=str(uuid.uuid4()))
            f.codes.add(concept_1)

        tree = lambda concept_id, negated=False: {
            "id": "a8889b8b-0123-4456-b89a-b189883fe954",
            "type": "group",
            "children1": [
                {
                    "type": "rule",
                    "id": "999ba8ab-0123-4456-b89a-b189883ff396",
                    "properties": {
                        "field": "codes",
                        "operator": "select_equals",
                        "value": [concept_id],
                        "valueSrc": [
                            "value"
                        ],
                        "valueType": [
                            "select"
                        ]
                    }
                }
            ],
            "properties": {
                "not": negated
            }
        }

        qs = tasks.translate_file_query('file', json.dumps(tree(concept_1.id_as_str)))
        assert n_files == qs.count()
        for f in qs:
            assert f.codes.count() == 1
            assert f.codes.first().code == concept_1.code

        qs = tasks.translate_file_query('file', json.dumps(tree(concept_1.id_as_str, negated=True)))
        assert 0 == qs.count()

    @pytest.mark.django_db
    def test_translate_query_file_set(self, user, project):
        concept_1 = 'concept_1'
        concept_2 = 'concept_2'
        cs = CodeSystem.objects.create(name='abc', uri='abc')
        concept_1 = Code.objects.create(code=concept_1, codesystem=cs)
        concept_2 = Code.objects.create(code=concept_2, codesystem=cs)
        fileset = FileSet.objects.create(name=str(uuid.uuid4()))
        n_files = 100
        for i in range(n_files):
            f = File.objects.create(created_by=user, name=str(uuid.uuid4()))
            if i < n_files / 2:
                f.codes.add(concept_1)
                fileset.files.add(f)
            else:
                f.codes.add(concept_2)

        tree = lambda concept_id: {
            "id": "a8889b8b-0123-4456-b89a-b189883fe954",
            "type": "group",
            "children1": [
                {
                    "type": "rule",
                    "id": "999ba8ab-0123-4456-b89a-b189883ff396",
                    "properties": {
                        "field": "filesets",
                        "operator": "select_equals",
                        "value": [fileset.id_as_str],
                        "valueSrc": [
                            "value"
                        ],
                        "valueType": [
                            "select"
                        ]
                    }
                },
                {
                    "type": "rule",
                    "id": "999ba8ab-0123-4456-b89a-b189883ff396",
                    "properties": {
                        "field": "codes",
                        "operator": "select_equals",
                        "value": [concept_id],
                        "valueSrc": [
                            "value"
                        ],
                        "valueType": [
                            "select"
                        ]
                    }
                }
            ]
        }
        qs = tasks.translate_file_query('file', json.dumps(tree(concept_1.id_as_str)))

        assert n_files / 2 == qs.count()
        for f in qs:
            assert f.codes.count() == 1
            assert f.codes.first().code == concept_1.code

    @pytest.mark.django_db
    def test_translate_query_operator_in(self, user, project):
        concept_1 = 'concept_1'
        concept_2 = 'concept_2'
        cs = CodeSystem.objects.create(name='abc', uri='abc')
        concept_1 = Code.objects.create(code=concept_1, codesystem=cs)
        concept_2 = Code.objects.create(code=concept_2, codesystem=cs)
        fileset = FileSet.objects.create(name=str(uuid.uuid4()))
        n_files = 100
        for i in range(n_files):
            f = File.objects.create(created_by=user, name=str(uuid.uuid4()))
            if i < n_files / 2:
                f.codes.add(concept_1)
                fileset.files.add(f)
            else:
                f.codes.add(concept_2)
                fileset.files.add(f)

        tree = {
            "id": "a8889b8b-0123-4456-b89a-b189883fe954",
            "type": "group",
            "children1": [
                {
                    "type": "rule",
                    "id": "999ba8ab-0123-4456-b89a-b189883ff396",
                    "properties": {
                        "field": "filesets",
                        "operator": "select_equals",
                        "value": [fileset.id_as_str],
                        "valueSrc": [
                            "value"
                        ],
                        "valueType": [
                            "select"
                        ]
                    }
                },
                {
                    "type": "rule",
                    "id": "999ba8ab-0123-4456-b89a-b189883ff396",
                    "properties": {
                        "field": "codes",
                        "operator": "select_any_in",
                        "value": [[concept_1.id_as_str, concept_2.id_as_str]],
                        "valueSrc": [
                            "value"
                        ],
                        "valueType": [
                            "select"
                        ]
                    }
                }
            ]
        }
        qs = tasks.translate_file_query('file', json.dumps(tree))

        assert n_files == qs.count()
        for f in qs:
            assert f.codes.count() == 1
            # assert f.concepts.first().concept == concept_1.concept or f.concepts.first().concept == concept_2.concept
