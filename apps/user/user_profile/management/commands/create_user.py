import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse

from apps.user.user_profile.models import Profile
from apps.utils import create_user_on_keycloak, get_node_origin, get_keycloak_admin, find_user_by_email


class Command(BaseCommand):
    help = "Creates a new user."

    def add_arguments(self, parser):
        """
        Adds command-line arguments for email and admin status.
        """
        # Argument for the user's email address. Optional.
        parser.add_argument(
            '--email',
            type=str,
            help="The email address for the new user."
        )
        # Argument to specify if the user should be an admin. Optional.
        parser.add_argument(
            '--is_admin',
            action='store_true',
            help="Set the user as an admin. If not provided, you will be prompted."
        )
        # Argument to specify if the user should NOT be an admin. This helps avoid ambiguity.
        parser.add_argument(
            '--no_admin',
            action='store_true',
            help="Explicitly set the user as a non-admin."
        )

    def handle(self, *args, **options):
        logging.info(settings.KEYCLOAK_URL)
        logging.info(settings.FIREFLY_API_URL)
        logging.info(settings.FIREFLY_WS_URL)
        data = {}

        username = options['email']
        is_admin_flag = options.get('is_admin')
        no_admin_flag = options.get('no_admin')

        # Get email from arguments or prompt the user
        if not username:
            username = input('Email address: ')

        # Determine admin status from arguments or prompt the user
        if is_admin_flag and no_admin_flag:
            self.stdout.write(self.style.ERROR("Error: Cannot use --is_admin and --no_admin flags simultaneously."))
            return

        if is_admin_flag:
            user_is_centauron_admin = True
        elif no_admin_flag:
            user_is_centauron_admin = False
        else:
            # Prompt if no admin flag was provided
            response = input('Should this user be an admin? [y/N]: ')
            user_is_centauron_admin = response.lower() == 'y'


        user_data = find_user_by_email(username)
        if user_data is not None:
            userid, did, user_identifier = user_data
            logging.info("User retrieved.")
        else:
            userid, did, user_identifier = create_user_on_keycloak(username, user_is_centauron_admin, email=username)
            logging.info("User created.")

        # on the first login, the user is added to this profile
        logging.info('Create user profile')
        qs = Profile.objects.filter(identity=did)
        if not qs.exists():
            profile = Profile.objects.create(
                identity=did,
                human_readable=username,
                # organization=data.get('organization'),
                # orcid=data.get('orcid'),
                # pubmed=data.get('pubmed'),
                # google_scholar=data.get('google_scholar'),
                node=get_node_origin(),
                identifier=user_identifier
            )
            profile.generate_private_key()
        else:
            profile = qs.first()

        logging.info('User profile created.')
        logging.info('Publishing...')
        # user must be published in order to be able to send submission etc.
        profile.publish_to_registry()
        logging.info('Published successfully.')

        keycloak_admin = get_keycloak_admin()

        logging.info('Send verification email.')
        keycloak_admin.send_verify_email(userid,
                                         client_id=settings.KEYCLOAK_CLIENT_ID)
        logging.info('Done.')
