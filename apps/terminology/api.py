from django.db import connection
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.terminology.models import Code


class TerminologyLookupView(APIView):

    def get(self, request, **kwargs):
        query = request.GET.get('query', None)
        if query is None:
            return Response(data=[])

        R = {'query': 'Unit', 'suggestions': []}

        max = 100
        # codes = Code.objects.filter(Q(human_readable__icontains=query) | Q(code__icontains=query))[:max]

        with connection.cursor() as cursor:
            # alternative queries to try:
            # f'select * from {Code.objects.model._meta.db_table} where levenshtein_less_equal(code, %s, 3) < 3'
            limit = 0.2
            # TODO allow search for code and also for label
            cmd = f'select code, id, codesystem_name, human_readable, round(l.sim::numeric, 4) from {Code.objects.model._meta.db_table},lateral ( select similarity(human_readable, %s) as sim) l where l.sim > {limit} order by l.sim desc'
            cursor.execute(
                cmd,
                [query])
            rows = cursor.fetchall()
            alternative_codes = tuple(map(lambda e: (e[1], e[2], e[0], e[3], e[4]), rows))

        for code in alternative_codes[:max]:
            R['suggestions'].append(dict(value=f'{code[3]} ({code[1]})', data=code[0]))

        return Response(data=R)
