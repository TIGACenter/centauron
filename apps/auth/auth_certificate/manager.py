from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class CertificateManager(models.Manager):

    def import_(self, token: Dict[str, Any]):
        sender = User.objects.get(username=token['issuer'])
        recipient = User.objects.get(username=token['recipient'])
        from apps.auth.auth_certificate.models import Certificate
        certi, _ = Certificate.objects.get_or_create(issued_by=sender, issued_for=recipient)
        certi.certificate = token['data']['certificate']
        return self.create(issued_by=sender, issued_for=recipient, certificate=token['data']['certificate'])
