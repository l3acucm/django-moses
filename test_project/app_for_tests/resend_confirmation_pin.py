from datetime import timedelta

from django.contrib.sites.models import Site
from django.test import TestCase
from django.utils.timezone import now

from moses.common import error_codes
from moses.views.user import UserViewSet
from test_project.app_for_tests import APIClient
from test_project.app_for_tests import utils

test_client = APIClient('')

PHONE = '+996507030927'


class ResendPhoneNumberConfirmationPinTestCase(TestCase):
    def setUp(self):
        self.confirm_phone_number_view = UserViewSet.as_view({'post': 'confirm_phone_number'})
        self.request_phone_number_pin_view = UserViewSet.as_view({'post': 'request_phone_number_confirmation_pin'})
        Site.objects.create(domain='wakamakafo.com')
        utils.SENT_SMS = {}
        utils.SENT_SMS_RAW = {}
        self.user, response = test_client.create_user(
            phone_number=PHONE, name='Q', password='secret!!1', email='fafa@gmail.com', domain='wakamakafo.com')
        self.assertEqual(response.status_code, 201)

    def _unlock_and_resend(self):
        self.user.phone_number_confirmation_code_sms_unlocks_at = now() - timedelta(seconds=1)
        self.user.save()
        self.user, response = test_client.request_phone_number_confirmation_pin(self.user)
        self.assertEqual(response.status_code, 200)

    def test_resend_sends_a_fresh_code_even_if_the_stored_one_was_wiped(self):
        # Saving the profile with an unchanged phone number zeroes the pin;
        # a resend used to deliver that "0".
        self.user.phone_number_confirmation_pin = 0
        self.user.save()
        self._unlock_and_resend()
        self.assertGreaterEqual(self.user.phone_number_confirmation_pin, 100000)
        self.assertEqual(utils.SENT_SMS[PHONE], self.user.phone_number_confirmation_pin)
        self.user, response = test_client.confirm_phone_number(self.user, str(utils.SENT_SMS[PHONE]))
        self.assertTrue(self.user.is_phone_number_confirmed)

    def test_resend_resets_the_attempts_limit(self):
        for _ in range(4):
            test_client.confirm_phone_number(
                self.user, utils.get_random_pin_non_equal_to(str(self.user.phone_number_confirmation_pin)))
        self.user.refresh_from_db()
        self.user, response = test_client.confirm_phone_number(self.user, str(self.user.phone_number_confirmation_pin))
        self.assertEqual(response.data['errors'][''][0]['error_code'], error_codes.ATTEMPTS_LIMIT_REACHED)

        self._unlock_and_resend()
        self.assertEqual(self.user.phone_number_confirmation_attempts, 0)
        self.user, response = test_client.confirm_phone_number(self.user, str(utils.SENT_SMS[PHONE]))
        self.assertTrue(self.user.is_phone_number_confirmed)

    def test_zero_pin_never_confirms(self):
        self.user.phone_number_confirmation_pin = 0
        self.user.save()
        for pin in ('', '0', '000000'):
            self.user, response = test_client.confirm_phone_number(self.user, pin)
            self.assertFalse(self.user.is_phone_number_confirmed, pin)

    def test_resend_without_candidate_sends_nothing_to_an_empty_number(self):
        self._unlock_and_resend()
        self.assertEqual(set(utils.SENT_SMS_RAW), {PHONE})
