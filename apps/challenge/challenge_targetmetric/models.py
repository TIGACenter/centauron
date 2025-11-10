import io
import uuid

import pandas
from django.db import models
from django.utils import timezone

from apps.challenge.models import Challenge
from apps.core.db_utils import insert_with_copy_from_and_tmp_table
from apps.core.models import Base, IdentifieableMixin


class TargetMetric(IdentifieableMixin, Base):
    class Order(models.TextChoices):
        ASC = 'asc'
        DESC = 'desc'

    class DType(models.TextChoices):
        INT = 'int'
        FLOAT = 'float'
        STR = 'string'

    sort = models.CharField(choices=Order.choices, null=True, max_length=4)
    key = models.CharField(max_length=200)
    dtype = models.CharField(choices=DType.choices, max_length=6, default=DType.FLOAT)
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='target_metrics')
    filename = models.CharField(max_length=100)
    name = models.CharField(max_length=100, null=True, blank=True, default=None)
    description = models.TextField(null=True, blank=True, default=None)

    def __str__(self):
        return f'{self.key} {self.sort}'

    @staticmethod
    def import_metric(share, target_metrics):
        if target_metrics is None: return

        df = pandas.read_csv(io.StringIO(target_metrics))
        now = timezone.now().isoformat()
        df['date_created'] = now
        df['last_modified'] = now

        identifiers = df['identifier'].to_list()
        qs = TargetMetric.objects.filter(identifier__in=identifiers).distinct()
        existing_files = {e[0]: e[1] for e in qs.values_list('identifier', 'id')}
        existing_rows = df['identifier'].isin(existing_files.keys())
        df['existing'] = existing_rows

        def fn_set_id(e):
            if not e['existing']: return str(uuid.uuid4())
            return existing_files[e['identifier']]
        print(df)
        df['id'] = df.apply(fn_set_id, axis=1)
        # filter out existing files
        df = df[~existing_rows]
        df = df.drop(columns=['existing'])

        challenge_cache = {}
        def fn_challenge(e):
            if e not in challenge_cache:
                challenge_cache[e] = Challenge.objects.get_by_identifier(e).id_as_str
            return challenge_cache[e]

        df['challenge'] = df['challenge'].apply(fn_challenge)
        df = df.rename(columns={'challenge': 'challenge_id'})

        insert_with_copy_from_and_tmp_table(df, TargetMetric.objects.model._meta.db_table)

        # TODO make targetmetric updatable
