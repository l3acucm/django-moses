
from guardian.conf import settings as guardian_settings
def get_init_anonymous_user_for_guardian(User):
    """
    Returns User model instance that would be referenced by guardian when
    permissions are checked against users that haven't signed into the system.

    :param User: User model - result of ``django.contrib.auth.get_user_model``.
    """
    kwargs = {
        User.USERNAME_FIELD: guardian_settings.ANONYMOUS_USER_NAME,
        "email": "fake@and.gay"
    }
    user = User(**kwargs)
    user.set_unusable_password()
    return user