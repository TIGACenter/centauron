from allauth.socialaccount.signals import social_account_added, social_account_updated
from django.contrib.auth.models import Group as DjangoGroup
from django.db import models
from django.dispatch import receiver

from apps.core.models import Base, IdentifieableMixin


class Group(IdentifieableMixin, Base):
    group = models.OneToOneField(DjangoGroup, on_delete=models.CASCADE, related_name="centauron_group")
    name = models.CharField(max_length=50, null=False, blank=False)


def update_account_role(user, groups, identifier, human_readable):
    is_admin = '/centauron-admin' in groups
    user.is_superuser = is_admin
    user.is_staff = is_admin
    user.save()
    user.profile.identifier = identifier
    user.profile.human_readable = human_readable
    user.profile.save()

@receiver(social_account_added)
def retrieve_social_data(request, sociallogin, **kwargs):
    """
    Synchronizes the keycloak group and the django group of a user. if the django group does not exist yet, it is created.
    """
    extra = sociallogin.account.extra_data
    identifier = extra.get('identifier')
    if "group" in extra:
        group_name = extra.get("group")[0][1:]
        g = Group.objects.filter(name=group_name)
        if not g.exists():
            django_group = DjangoGroup.objects.create(name=group_name)
            group = Group.objects.create(name=group_name, group=django_group)
            sociallogin.account.user.groups.add(django_group)
        else:
            group = g.first()
        sociallogin.account.user.profile.groups.add(group)

        update_account_role(sociallogin.account.user, extra.get('group', []), identifier, extra.get('preferred_username'))


@receiver(social_account_updated)
def update_social_data(request, sociallogin, **kwargs):
    extra = sociallogin.account.extra_data
    identifier = extra.get('identifier')
    update_account_role(sociallogin.account.user, extra.get('group', []), identifier, extra.get('preferred_username'))
