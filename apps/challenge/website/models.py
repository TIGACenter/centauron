from django.db import models
from django.urls import reverse

from apps.core.models import CreatedByMixin, IdentifieableMixin, Base


class ChallengeWebsite(CreatedByMixin, IdentifieableMixin, Base):
    challenge = models.OneToOneField('challenge.Challenge', on_delete=models.CASCADE, related_name='website')

    slogan = models.TextField(blank=True, null=True)
    hero = models.TextField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    affiliation = models.TextField(blank=True, null=True)

    def get_absolute_url(self):
        return reverse('project:website:preview', kwargs={'pk': self.project_id, 'website_pk': self.pk})
