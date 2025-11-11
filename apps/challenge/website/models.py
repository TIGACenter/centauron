from django.db import models
from django.urls import reverse

from apps.core.models import CreatedByMixin, IdentifieableMixin, Base


class ChallengeWebsite(CreatedByMixin, IdentifieableMixin, Base):
    challenge = models.OneToOneField('challenge.Challenge', on_delete=models.CASCADE, related_name='website')

    slogan = models.TextField(blank=True, null=True)
    hero = models.TextField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    affiliation = models.TextField(blank=True, null=True)
    selected_endpoints = models.JSONField(default=list, blank=True, help_text="List of selected endpoint names to display on the website")
    citation = models.TextField(blank=True, null=True, help_text="Citation text for the challenge/dataset")
    bibtex = models.TextField(blank=True, null=True, help_text="BibTeX citation for the challenge/dataset")

    def get_absolute_url(self):
        return reverse('challenge:website:preview', kwargs={'pk': self.challenge_id, 'website_pk': self.pk})
