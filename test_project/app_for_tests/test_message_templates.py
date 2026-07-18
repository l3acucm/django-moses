from datetime import timedelta

from django.conf import settings as django_settings
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from django.utils.timezone import now

from moses.models import CustomUser
from moses.services.messages import render_message
from moses.views.user import UserViewSet
from test_project.app_for_tests import APIClient
from test_project.app_for_tests import utils


def make_user(**kwargs):
    kwargs.setdefault("preferred_language", "en")
    return CustomUser(**kwargs)


def test_default_phone_confirmation_body_contains_pin():
    user = make_user()
    result = render_message("PHONE_NUMBER_CONFIRMATION_PIN_BODY", user, pin=123456)
    assert "123456" in result


def test_partial_override_uses_custom_key_and_default_for_the_rest():
    user = make_user()
    with override_settings(
        MOSES={"MESSAGE_TEMPLATES": {"PHONE_NUMBER_CONFIRMATION_PIN_BODY": "{pin}"}}
    ):
        sms = render_message("PHONE_NUMBER_CONFIRMATION_PIN_BODY", user, pin=123456)
        email = render_message("EMAIL_CONFIRMATION_PIN_BODY", user, pin=123456)
    assert sms == "123456"  # overridden -> bare code
    assert email != "123456" and "123456" in email  # untouched default


def test_override_does_not_leak_into_defaults_after_reload():
    user = make_user()
    with override_settings(
        MOSES={"MESSAGE_TEMPLATES": {"PHONE_NUMBER_CONFIRMATION_PIN_BODY": "{pin}"}}
    ):
        render_message("PHONE_NUMBER_CONFIRMATION_PIN_BODY", user, pin=1)
    # settings reload to defaults on context exit; module default must be intact
    restored = render_message("PHONE_NUMBER_CONFIRMATION_PIN_BODY", user, pin=1)
    assert restored != "1"


def test_user_attribute_placeholder_is_substituted():
    user = make_user(first_name="Alice")
    with override_settings(
        MOSES={"MESSAGE_TEMPLATES": {"EMAIL_CONFIRMATION_PIN_BODY": "Hi {user.first_name}: {pin}"}}
    ):
        result = render_message("EMAIL_CONFIRMATION_PIN_BODY", user, pin=99)
    assert result == "Hi Alice: 99"


def test_password_reset_sms_and_email_bodies_are_independent():
    user = make_user()
    with override_settings(
        MOSES={"MESSAGE_TEMPLATES": {"PASSWORD_RESET_SMS_BODY": "{pin}"}}
    ):
        sms = render_message("PASSWORD_RESET_SMS_BODY", user, pin=555)
        email = render_message("PASSWORD_RESET_EMAIL_BODY", user, pin=555)
    assert sms == "555"
    assert email != "555" and "555" in email


def test_notification_body_substitutes_domain():
    user = make_user()
    result = render_message("PASSWORD_CHANGED_BODY", user, domain="cashway.example")
    assert "cashway.example" in result


test_client = APIClient('')


class SmsOnlyCodeE2ETestCase(TestCase):
    """Headline business requirement: with the SMS template overridden to
    '{pin}', the outgoing SMS body is the bare code — no extra text."""

    def setUp(self):
        Site.objects.create(domain='wakamakafo.com')
        utils.SENT_SMS = {}
        utils.SENT_SMS_RAW = {}

    def test_phone_confirmation_sms_contains_only_the_code(self):
        merged_moses = {
            **django_settings.MOSES,
            "MESSAGE_TEMPLATES": {"PHONE_NUMBER_CONFIRMATION_PIN_BODY": "{pin}"},
        }
        with override_settings(MOSES=merged_moses):
            user, response = test_client.create_user(
                phone_number='+996507030927',
                name='Q',
                password='secret!!1',
                email='fafa@gmail.com',
                domain='wakamakafo.com',
            )
            self.assertEqual(response.status_code, 201)
            user.phone_number_confirmation_code_sms_unlocks_at = now() - timedelta(days=1)
            user.save()
            user, response = test_client.request_phone_number_confirmation_pin(user)
            self.assertEqual(response.status_code, 200)

        raw = utils.SENT_SMS_RAW['+996507030927']
        self.assertEqual(raw, str(utils.SENT_SMS['+996507030927']))
        self.assertTrue(raw.isdigit())
