from django.db import models, transaction
import yaml

from apps.core.managers import BaseManager
from apps.core.models import CreatedByMixin, IdentifieableMixin, Base
from apps.federation.messages import GroundTruthSchemaContent, Message, GroundTruthSchemaObject
from apps.federation.outbox.models import OutboxMessage
from apps.project.models import Project


class GroundTruthManager(BaseManager):
    pass


class GroundTruth(CreatedByMixin, IdentifieableMixin, Base):
    objects = GroundTruthManager()
    content = models.TextField(blank=True, default='')
    nr_rows = models.IntegerField(blank=True, default=0)
    nr_columns = models.IntegerField(blank=True, default=0)
    schema = models.ForeignKey('GroundTruthSchema', on_delete=models.CASCADE, related_name='ground_truths')

    def __str__(self):
        return f'{self.pk}'

class GroundTruthSchemaManager(BaseManager):
    pass


class GroundTruthSchema(CreatedByMixin, IdentifieableMixin, Base):
    objects = GroundTruthSchemaManager()
    name = models.CharField(max_length=200)
    yaml = models.TextField(blank=True, default='')
    project = models.ForeignKey('project.Project', on_delete=models.CASCADE, related_name='ground_truth_schemas')
    is_distributed = models.BooleanField(default=False)


    def __str__(self):
        return self.id_as_str

    def get_endpoints(self):
        """
        Extract clinical endpoints from the YAML schema.
        Returns a list of dictionaries with 'name' and 'description' keys.
        Only includes columns where is_endpoint is True.
        """
        endpoints = []
        if not self.yaml:
            return endpoints

        try:
            schema_data = yaml.safe_load(self.yaml)
            if isinstance(schema_data, dict):
                # Iterate through each column (top-level keys in the schema)
                for column_id, column_props in schema_data.items():
                    if isinstance(column_props, dict) and column_props.get('is_endpoint', False):
                        endpoints.append({
                            'name': column_props.get('name', column_id),
                            'description': column_props.get('description', ''),
                        })
        except yaml.YAMLError:
            # If YAML parsing fails, return empty list
            pass

        return endpoints

    def to_message_object(self) -> GroundTruthSchemaObject:
        return GroundTruthSchemaObject(content=GroundTruthSchemaContent(identifier=self.identifier,
                                        name=self.name,
                                        yaml=self.yaml,
                                        project=self.project.identifier))

    def distribute(self):
        message_object = self.to_message_object()
        for member in self.project.get_project_members():
            om = OutboxMessage.create(recipient=member.user,
                                      sender=self.created_by,
                                      message_object=message_object)
            om.send()

        self.is_distributed = True
        self.save(update_fields=['is_distributed'])

    @staticmethod
    def import_ground_truth(**kwargs):
        message: Message = kwargs['message']
        o: GroundTruthSchemaObject = message.object

        with transaction.atomic():
            content: GroundTruthSchemaContent = GroundTruthSchemaContent(**o.content)
            # TODO what if project is not found??
            project = Project.objects.get_by_identifier(content.project)
            GroundTruthSchema.objects.create(
                identifier=content.identifier,
                name=content.name,
                project=project,
                yaml=content.yaml
            )
