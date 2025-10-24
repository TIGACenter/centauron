from django.contrib import auth
from django.contrib.auth import authenticate
from django.utils.deprecation import MiddlewareMixin


class SSOMiddleware(MiddlewareMixin):

    def process_request(self, request):
        jwt = request.META.get('HTTP_AUTHORIZATION', None)
        if jwt is None:
            jwt = request.META.get('HTTP_X_FORWARDED_JWT', None)

        if jwt is not None:
            user = authenticate(request, token=jwt)
            if user:
                request.user = user
                auth.login(request, user)
            # else:
            #     raise PermissionDenied()



