"""
Moses signals

These signals are emitted during authentication and credential confirmation flows.
"""
from django.dispatch import Signal


# Signal emitted when a user successfully confirms their phone number
# Provides:
#   - sender: The User model class
#   - user: The user instance whose phone was confirmed
#   - phone_number: The confirmed phone number (str)
#   - is_initial_confirmation: True if this is the first confirmation, False if updating phone
phone_number_confirmed = Signal()


# Signal emitted when a user successfully confirms their email
# Provides:
#   - sender: The User model class
#   - user: The user instance whose email was confirmed
#   - email: The confirmed email address (str)
#   - is_initial_confirmation: True if this is the first confirmation, False if updating email
email_confirmed = Signal()
