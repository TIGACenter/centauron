from django.conf import settings
from keycloak import KeycloakOpenID

keycloak_openid = KeycloakOpenID(server_url=settings.KEYCLOAK_URL,
                                 client_id=settings.KEYCLOAK_CLIENT_ID,
                                 realm_name=settings.KEYCLOAK_REALM,
                                 client_secret_key=settings.KEYCLOAK_CLIENT_SECRET)


def get_service_account_jwt():
    token = keycloak_openid.token(settings.KEYCLOAK_CLIENT_ID, settings.KEYCLOAK_CLIENT_SECRET,
                                  grant_type='client_credentials')
    return token['access_token']


def refresh_jwt(refresh_token: str):
    return keycloak_openid.refresh_token(refresh_token)['access_token']


def get_identifier_from_jwt(jwt: str) -> str:
    options = {"verify_signature": False,
               "verify_aud": False,
               "verify_exp": False,
               "verify_at_hash": False
               }
    token_info = keycloak_openid.decode_token(jwt, key=settings.KEYCLOAK_PUBLIC_KEY, options=options)
    return token_info.get('identifier', None)
