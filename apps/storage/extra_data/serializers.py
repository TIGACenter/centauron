from rest_framework import serializers

from apps.storage.extra_data.models import ExtraData


class ExtraDataSerializer(serializers.ModelSerializer):
    payload = serializers.JSONField()
    event = serializers.CharField()

    class Meta:
        model = ExtraData
        fields = ('description','payload', 'event',)
