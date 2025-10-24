from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import get_object_or_404

from apps.user.user_profile.models import Profile
from apps.utils import get_node_origin


class CentauronSocialAccountAdapter(DefaultSocialAccountAdapter):

    def save_user(self, request, sociallogin, form=None):
        R = super().save_user(request, sociallogin, form)

        node = get_node_origin()
        data = sociallogin.account.extra_data
        self.set_user_data(R, node, data)
        return R

    def set_user_data(self, R, node, data):
        is_superuser = '/centauron-admin' in data.get('groups', [])
        R.is_superuser = is_superuser
        R.is_staff = is_superuser
        R.save(update_fields=['is_superuser', 'is_staff'])

        p = get_object_or_404(Profile, node=node, identity=data['did'], identifier=data['identifier'])
        if p.user is None:
            p.user = R
            p.save()

    # def populate_user(self, request, sociallogin, data):
    #     user = sociallogin.user
    #     extra_data = sociallogin.account.extra_data
    #     self.set_user_data(user, user, extra_data)
    #     return super().populate_user(request, sociallogin, data)
