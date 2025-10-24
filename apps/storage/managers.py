from django.db import models

from apps.core.managers import BaseManager


class FileManager(BaseManager):
    def search(self, identifiers):
        i = [(e.system, e.value) for e in identifiers]
        systems = [e[0] for e in i]
        values = [e[1] for e in i]
        return self.filter(identifier__system__in=systems, identifier__value__in=values)
