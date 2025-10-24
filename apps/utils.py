import json
import logging
import random
import string
import uuid
from typing import Tuple, Dict, Optional

from django.conf import settings
from keycloak import KeycloakOpenIDConnection, KeycloakAuthenticationError, KeycloakAdmin

from apps.blockchain.utils import create_keystore, add_identity_to_ff_signer, create_identity
from apps.core import identifier
from apps.node.models import Node
from apps.user.user_profile.models import Profile
import re


def get_node_origin() -> Node:
    return Node.objects.get(identifier=settings.IDENTIFIER)

def get_user_node() -> Profile:
    return Profile.objects.get(user__username='node')

def get_keycloak_admin_password() -> str:
    with settings.KEYCLOAK_ADMIN_PASSWORD.open('r') as f:
        return f.read().strip()

def get_keycloak_connection():
    try:
        with settings.KEYCLOAK_ADMIN_CONFIG.open() as f:
            config = json.load(f)

        return KeycloakOpenIDConnection(
            server_url=settings.KEYCLOAK_URL,
            username=settings.KEYCLOAK_ADMIN_USERNAME,
            password=get_keycloak_admin_password(),
            user_realm_name=config.get('realm'),
            realm_name=settings.KEYCLOAK_REALM,
            client_id=config.get('resource'),
            client_secret_key=config.get('credentials').get('secret'),
            verify=True)
    except KeycloakAuthenticationError as e:
        raise e

def get_keycloak_admin():
    return KeycloakAdmin(connection=get_keycloak_connection())

def generate_random_password():
    characters = string.ascii_letters + string.digits
    password = ''.join(random.choice(characters) for _ in range(10))
    return password

def sanitize_email_to_username(email):
    """Sanitizes an email into a username by replacing '@' with '.' and ensuring it follows naming rules."""

    # Replace '@' with '.'
    username = email.replace("@", ".")

    # Remove disallowed characters (only keep a-z, A-Z, 0-9, ., -, _)
    username = re.sub(r"[^a-zA-Z0-9._-]", "", username)

    # Ensure it starts and ends with an alphanumeric character
    username = re.sub(r"^[^a-zA-Z0-9]+", "", username)  # Remove leading non-alphanumeric
    username = re.sub(r"[^a-zA-Z0-9]+$", "", username)  # Remove trailing non-alphanumeric

    # Enforce length limit (1-64 chars)
    if not username or len(username) > 64:
        username = username[:63]

    return username


def create_firefly_identity(temp_pw:str, userid, username) -> str:
    logging.info('Creating keystore...')
    username = sanitize_email_to_username(username)
    keystore = create_keystore(temp_pw)
    logging.info('Add keystore to firefly signer...')
    add_identity_to_ff_signer(temp_pw, keystore)
    logging.info('Announce identity to network...')
    did = create_identity(userid, username, keystore['address'])
    logging.info(f'Wallet created with password: {temp_pw} (note it down now, it will never be shown again).')
    return did

def create_user_on_keycloak(username, is_admin: bool=False, email:str|None=None, attributes: Dict[str,str]=None) -> Tuple[str,str, str]:
    try:
        keycloak_admin = get_keycloak_admin()
    except KeycloakAuthenticationError as e:
        raise e

    # TODO store temp password somewhere
    temp_pw = generate_random_password()

    # userid = str(uuid.uuid4())
    # did = f'did:{userid}' # create_firefly_identity(temp_pw, userid, username)

    user_identifier = identifier.create_random('user')
    did = user_identifier
    default_attributes = {
            "identifier": [user_identifier],
            'did': did
        }
    if attributes is not None:
        default_attributes = {**attributes, **default_attributes}

    payload = {
        "username": username,
        "enabled": True,
        "attributes": default_attributes,
        # "requiredActions": ["verify-email"]
    }
    if email is not None:
        payload['email'] = email

    new_user_id = keycloak_admin.create_user(payload, exist_ok=False)
    keycloak_admin.set_user_password(new_user_id, temp_pw, temporary=True)

    if is_admin:
        groups = keycloak_admin.get_groups({'search': 'centauron-admin', 'exact': True})
        keycloak_admin.group_user_add(new_user_id, groups[0]['id'])

    return new_user_id, did, user_identifier


def find_user_by_email(email: str) -> Optional[Tuple[str, str, str]]:
    """
    Checks if a user exists in Keycloak with a given email address.

    Args:
        email: The email address to search for.

    Returns:
        A tuple containing (user_id, did, user_identifier) if the user is found
        and has the required attributes. Otherwise, returns None.

    Raises:
        KeycloakAuthenticationError: If authentication with Keycloak fails.
    """
    if not email:
        return None

    try:
        keycloak_admin = get_keycloak_admin()
    except KeycloakAuthenticationError as e:
        # Propagate authentication errors to the caller
        raise e

    # Search for users with an exact email match.
    # This returns a list, which will be empty if no user is found.
    users = keycloak_admin.get_users({"email": email, "exact": True})

    if not users:
        # No user found with that email, return None
        return None

    # User was found, so we take the first result from the list.
    user_data = users[0]

    # Safely extract the required information
    user_id = user_data.get('id')
    attributes = user_data.get('attributes', {})

    # In Keycloak, all custom attributes are stored as lists.
    # We safely get the first item from the list or None if it's missing/empty.
    did_list = attributes.get('did', [])
    identifier_list = attributes.get('identifier', [])

    did = did_list[0] if did_list else None
    user_identifier = identifier_list[0] if identifier_list else None

    # Only return the tuple if all three essential pieces of information are present.
    if user_id and did and user_identifier:
        return user_id, did, user_identifier

    # The user was found but is missing the required 'did' or 'identifier' attributes.
    return None
