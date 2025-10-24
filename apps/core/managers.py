from django.db import models



class BaseManager(models.Manager):

    def get_by_identifier(self, identifier: str, **kwargs):
        if identifier is None:
            raise ValueError('Given identifier is None.')
        return self.get(identifier=identifier, **kwargs)

    def filter_by_identifier(self, identifier: str, **kwargs):
        return self.filter(identifier=identifier, **kwargs)

    def filter_by_identifiers(self, identifiers: list[str]):
        return self.filter(identifier__in=identifiers)

    def for_user(self, user):
        '''

        :param user: type is Profile
        :return:
        '''
        return self.filter(created_by=user)
