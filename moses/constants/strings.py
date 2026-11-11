from django.utils.translation import gettext_lazy as _

# --- Credential confirmation (PIN) ---
EMAIL_CONFIRMATION_PIN_TITLE = _("Email confirmation PIN")
EMAIL_CONFIRMATION_PIN_BODY = _("Your email confirmation PIN is {pin}")
PHONE_NUMBER_CONFIRMATION_PIN_BODY = _("Your phone number confirmation PIN is {pin}")

# --- Password reset (email and SMS are separate on purpose) ---
PASSWORD_RESET_PIN_TITLE = _("Password reset")
PASSWORD_RESET_EMAIL_BODY = _("Your password reset PIN is {pin}")
PASSWORD_RESET_SMS_BODY = _("Your password reset PIN is {pin}")

# --- Notification emails ---
PASSWORD_CHANGED_TITLE = _("Password changed")
PASSWORD_CHANGED_BODY = _(
    "Your password has been changed. "
    "If it happened without your desire - contact us by email support@{domain}."
)
EMAIL_CHANGED_TITLE = _("Email changed")
EMAIL_CHANGED_BODY = _(
    "Your email has been changed. "
    "If it happened without your desire - contact us by email support@{domain}."
)
PHONE_NUMBER_CHANGED_TITLE = _("Phone number changed")
PHONE_NUMBER_CHANGED_BODY = _(
    "Your phone number has been changed. "
    "If it happened without your desire - contact us by email support@{domain}."
)

# Default templates exposed via the MESSAGE_TEMPLATES setting. Projects override
# any subset of these keys through their MOSES = {"MESSAGE_TEMPLATES": {...}}.
DEFAULT_MESSAGE_TEMPLATES = {
    "EMAIL_CONFIRMATION_PIN_TITLE": EMAIL_CONFIRMATION_PIN_TITLE,
    "EMAIL_CONFIRMATION_PIN_BODY": EMAIL_CONFIRMATION_PIN_BODY,
    "PHONE_NUMBER_CONFIRMATION_PIN_BODY": PHONE_NUMBER_CONFIRMATION_PIN_BODY,
    "PASSWORD_RESET_PIN_TITLE": PASSWORD_RESET_PIN_TITLE,
    "PASSWORD_RESET_EMAIL_BODY": PASSWORD_RESET_EMAIL_BODY,
    "PASSWORD_RESET_SMS_BODY": PASSWORD_RESET_SMS_BODY,
    "PASSWORD_CHANGED_TITLE": PASSWORD_CHANGED_TITLE,
    "PASSWORD_CHANGED_BODY": PASSWORD_CHANGED_BODY,
    "EMAIL_CHANGED_TITLE": EMAIL_CHANGED_TITLE,
    "EMAIL_CHANGED_BODY": EMAIL_CHANGED_BODY,
    "PHONE_NUMBER_CHANGED_TITLE": PHONE_NUMBER_CHANGED_TITLE,
    "PHONE_NUMBER_CHANGED_BODY": PHONE_NUMBER_CHANGED_BODY,
}
