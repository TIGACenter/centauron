from django.contrib.auth.models import User



def create_user(username):
    created_by_user = User.objects.create(username=username)
    created_by_user.profile.identifier = username
    created_by_user.profile.save()
    return created_by_user
