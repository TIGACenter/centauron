from rest_framework import serializers

from apps.share.models import Share


class ShareSerializer(serializers.ModelSerializer):
    origin = serializers.StringRelatedField(read_only=True)
    identifier = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Share
        fields = ('content', 'origin', 'name', 'identifier', 'description')
