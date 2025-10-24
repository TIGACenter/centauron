from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.core import identifier
from apps.core.models import Annotation


class IdentifierField(serializers.Field):
    def to_representation(self, obj):
        return str(obj.identifier)

    def to_internal_value(self, data):
        try:
            i = identifier.from_string(data)
            if i is None:
                raise ValidationError(f'{data} is not a valid identifier.')
            return i
        except Exception as e:
            raise e

class OriginField(serializers.RelatedField):
    def to_representation(self, obj):

        return str(obj.identifier)

class AnnotationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Annotation
        fields = ('system', 'value', 'readable')

class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)
        exclude_fields = kwargs.pop('exclude_fields', None)

        # Instantiate the superclass normally
        super().__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        if exclude_fields is not None:
            for field_name in exclude_fields:
                if field_name in self.fields:
                    self.fields.pop(field_name)
