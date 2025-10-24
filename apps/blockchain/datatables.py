from rest_framework import serializers

from apps.blockchain.models import Log
from apps.core.drf_mixins import DataTableViewSetBase


class LogSerializer(serializers.ModelSerializer):
    class Meta:
        datatables_always_serialize = ('id',)
        model = Log
        fields = '__all__'


class LogDataTableView(DataTableViewSetBase):
    serializer_class = LogSerializer

    def get_queryset(self):
        return Log.objects.order_by('-date_created')
