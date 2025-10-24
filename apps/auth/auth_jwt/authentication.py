import logging
from rest_framework import authentication
from rest_framework.exceptions import NotAuthenticated

from apps.auth.authentication import CentauronAuth


class JWTAuthentication(CentauronAuth, authentication.BaseAuthentication):
    '''
    This backend is for authentication against a rest api.
    '''

    def authenticate(self, request, **kwargs):
        # get token in kwargs issued by the SSOMiddleware
        # for drf the token is not anymore in kwargs, so check again the authorization header.
        token = kwargs.get('token', request.META.get('HTTP_AUTHORIZATION', None))
        if token is None:
            return None

        try:
            type, jwt = token.split(' ')
            if type != 'Bearer':
                return None
        except Exception as e:
            logging.exception(e)
            return None

        try:
            check_jwt = super().check_jwt(jwt, {"verify_signature": True,
                                                "verify_aud": False,
                                                "verify_exp": True,
                                                'verify_at_hash': False})
            return check_jwt
        except Exception as e:
            raise NotAuthenticated(e)


