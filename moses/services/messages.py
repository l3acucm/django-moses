from django.utils import translation

from moses.conf import settings as moses_settings


def render_message(key: str, user, *, pin=None, **extra) -> str:
    """Render a MESSAGE_TEMPLATES entry for ``user``.

    The template is resolved to the user's ``preferred_language`` (via
    gettext_lazy) and then formatted with ``str.format``. ``{pin}``, ``{user}``
    (and its attributes, e.g. ``{user.name}``) and ``{domain}`` are always
    available; callers add anything else through ``extra``.
    """
    template = moses_settings.MESSAGE_TEMPLATES[key]
    context = {"user": user, "pin": pin, "domain": moses_settings.DOMAIN, **extra}
    with translation.override(user.preferred_language):
        return str(template).format(**context)
