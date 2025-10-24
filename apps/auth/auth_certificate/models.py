from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import models

# Create your models here.
from typing import Dict, Any

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.auth.auth_certificate.exceptions import UserNotImportedException
from apps.auth.auth_certificate.manager import CertificateManager
from apps.core import identifier
from apps.core.models import Base
from apps.federation import cert_utils
from apps.federation.messages import CertificateMessage, CertificateMessageContent
from apps.share.share_token import token_utils
from apps.user.user_profile.models import Profile

User = get_user_model()


class Certificate(Base):
    objects = CertificateManager()

    issued_by = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE,
                                  related_name='certificates_issued')
    issued_for = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE, related_name='certificates')
    certificate = models.TextField(null=False)
    valid_until = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['issued_by', 'issued_for'], name='unique_issued_by_issued_for')]

    def __str__(self):
        # if self.issued_by is not None and self.issued_by.data is not None and self.issued_for is not None and self.issued_for.data is not None:
        #     return f'Issued_by: {self.issued_by.data.common_name}, Issued_for: {self.issued_for.data.common_name}'
        return super().__str__()

    @staticmethod
    def create_from_csr(csr: str,
                        issued_by: Profile,
                        issued_for: Profile) -> 'Certificate':
        # sign csr
        valid_for_days = 365
        cert = cert_utils.sign_csr(valid_for_days, csr)
        certi, created = Certificate.objects.get_or_create(issued_by=issued_by,
                                                           issued_for=issued_for,
                                                           certificate=cert,
                                                           valid_until=timezone.now() + timedelta(days=valid_for_days))
        return certi

    def as_token(self) -> str:
        message =  CertificateMessage(
            content=CertificateMessageContent(
                certificate=self.certificate,
                valid_until=self.valid_until,
                recipient=str(self.issued_for.identifier),
                issuer=str(self.issued_by.identifier),
            )
        )
        return token_utils.create_token('Certificate', f'Certificate for {self.issued_for.identifier}', message.json())


    @staticmethod
    def import_certificate(message:CertificateMessage):

        try:
            sender = Profile.objects.get_by_identifier(identifier.from_string(message.content.issuer))
            issued_for = Profile.objects.get_by_identifier(identifier.from_string(message.content.recipient))
        except Profile.DoesNotExist as e:
            raise UserNotImportedException('Issuer or recipient not imported yet. Import user before importing a certificate.')
        qs = Certificate.objects.filter(issued_by=sender, issued_for=issued_for) # TODO filter for only valid certs?
        if qs.exists():
            cert = qs.first()
            cert.certificate = message.content.certificate
            cert.valid_until = message.content.valid_until
            cert.save()
        else:
            Certificate.objects.create(issued_by=sender, issued_for=issued_for, certificate=message.content.certificate, valid_until=message.content.valid_until)
