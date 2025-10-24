from rest_framework import serializers

from apps.storage.models import File


class TileSetFileTableSerializer(serializers.ModelSerializer):
    href = serializers.SerializerMethodField()
    case = serializers.SlugRelatedField(read_only=True, slug_field='name')
    origin = serializers.SlugRelatedField(read_only=True, slug_field='human_readable')
    originating_from = serializers.SlugRelatedField(read_only=True, slug_field='name')

    class Meta:
        datatables_always_serialize = ('id', 'href',)
        model = File
        fields = ('id', 'href', 'case', 'origin', 'originating_from', 'name')

    def get_href(self, obj: File) -> str:
        return '#'
