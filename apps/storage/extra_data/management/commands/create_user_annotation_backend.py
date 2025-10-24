from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token

User = get_user_model()


class Command(BaseCommand):
    help = "Creates the user that is authorized to create ExtraData entities from the annotation backend."

    def handle(self, *args, **options):
        username = settings.ANNOTATION_BACKEND_USERNAME
        user, created = User.objects.get_or_create(username=username)  # no password so user cannot sign in
        if not created:
            self.stdout.write('user already exists. exiting.')
            return
        self.stdout.write(f'User {username} created.')
        token, _ = Token.objects.update_or_create(user=user)
        self.stdout.write(f'Token created for user {user}.')
        self.stdout.write(f'Done.')
