import uuid

from django.db import models


class Base(models.Model):
    class Meta:
        abstract = True

    date_created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    @property
    def id_as_str(self):
        return str(self.id)


class IdentifieableMixin(Base):
    identifier = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        if self.identifier is not None:
            return str(self.identifier)
        return super().__str__()

    # TODO override in order to create an identifier if none was created yet
    # def save(
    #     self,
    #     **kwargs
    # ) -> None:
    #     if self.identifier is None:
    #


class Annotation(Base):
    system = models.CharField(max_length=400)
    value = models.TextField()
    readable = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.system}#{self.value}'


class CreatedByMixin(models.Model):
    class Meta:
        abstract = True

    created_by = models.ForeignKey(
        'user_profile.Profile',
        on_delete=models.CASCADE,
        default=None,
        null=True,
        blank=True,
        related_name="%(class)s_created_by",
    )


class OriginMixin(models.Model):
    class Meta:
        abstract = True

    # TODO origin chains??

    origin = models.ForeignKey('user_profile.Profile', null=True, related_name='%(class)s_origin',
                               on_delete=models.SET_NULL)


class CodeListMixin(models.Model):
    class Meta:
        abstract = True

    codes = models.ManyToManyField('terminology.Code', related_name='%(class)s_codes', blank=True)

    def code_list(self):
        return [c for c in self.codes.all()]

    def code_list_string_rep(self):
        return [c.get_readable_str() for c in self.code_list()]

    def code_list_code_rep(self):
        return [c.code for c in self.code_list()]

    def code_list_identifier_rep(self):
        return [c.get_machine_rep() for c in self.code_list()]


class BaseResource(CodeListMixin, Base):
    class Meta:
        abstract = True

    """
    This field can be used to add metadata to any resource.
    """
    annotations = models.ManyToManyField(Annotation, related_name="%(class)s_annotations", blank=True)

    # def __str__(self):
    #     if self.identifier.exists():
    #         return str(self.identifier.first())
    #     return super().__str__()
