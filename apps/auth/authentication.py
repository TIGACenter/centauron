import logging
from typing import Dict, Any

import loguru
from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User, Group as DjangoGroup
from django.core.exceptions import PermissionDenied

from apps.auth.keycloak import keycloak_openid
from apps.user.user_group.models import Group


class CentauronAuth:

    def check_token_info(self, token_info: Dict[str, Any]):
        pass

    def check_jwt(self, jwt, verify_opts: Dict[str, bool] = None):
        KEYCLOAK_PUBLIC_KEY = "-----BEGIN PUBLIC KEY-----\n" + settings.KEYCLOAK_PUBLIC_KEY + "\n-----END PUBLIC KEY-----"
        # actually we don't have to check anything here anymore as it is done by traefik. just to be sure validate jwt again.
        options = {"verify_signature": False,
                   "verify_aud": False, "verify_exp": True,
                   'verify_at_hash': False}
        if verify_opts is not None:
            options = {**options, **verify_opts}
        try:
            token_info = keycloak_openid.decode_token(jwt, key=KEYCLOAK_PUBLIC_KEY, options=options, access_token=jwt)
            # this can be used to check additional data in an application by simply overwriting the jwtauthentication class.
            self.check_token_info(token_info)
            # identifier = token_info.get('identifier', None)
            # if identifier is None:
            #     return None
            # no need for password. user is legitimated by verify_signature and verify_exp.
            user, _ = User.objects.get_or_create(username=token_info['preferred_username'])
            # TODO add the user's name from jwt as the name in the profile? better for displaying...
            user.is_superuser = token_info.get('centauron_admin', False)
            user.is_staff = user.is_superuser
            # user.userprofile.identifier =
            user.save()

            # print(token_info)
            # if 'group_identifier' in token_info:
            #     group_identifier_str = token_info.get('group_identifier', None)
            #     group_identifier = group_identifier_str # Identifier.objects.from_string(group_identifier_str)
            #     django_group, _ = DjangoGroup.objects.get_or_create(name=group_identifier_str)
            #     Group.objects.get_or_create(name=group_identifier_str, group=django_group,
            #                                 identifier=group_identifier)
            #     user.groups.add(django_group)
            #
            #
            # if user.profile.identifier is None:
            #     user.profile.identifier = identifier # Identifier.objects.from_string(identifier)
            #     user.profile.save()
            return user, user.profile
        except Exception as e:
            logging.exception(e)
            raise e
            # # return None
            # raise NotAuthenticatedError()


class SSOAuthenticationBackend(CentauronAuth, BaseBackend):
    '''
    This backend is for authentication against the user browser session.
    '''

    def authenticate(self, request, **kwargs):
        token = kwargs.get('token', None)
        if token is None:
            return None
        try:
            type, jwt = token.split(' ')
            if type != 'Bearer':
                return None
        except Exception as e:
            logging.warning(e)
            return None
        try:
            user = super().check_jwt(jwt, {"verify_signature": False,
                                           "verify_aud": False,
                                           "verify_exp": True,
                                           'verify_at_hash': False})
            if user is None:
                return None
            return user[0]  # do not return profile here
        except Exception as e:
            raise PermissionDenied(e)

    def get_user(self, user_id):
        qs = User.objects.filter(pk=user_id)
        if not qs.exists():
            return None
        return qs.first()

