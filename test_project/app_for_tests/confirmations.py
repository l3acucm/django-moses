from datetime import timedelta

import pyotp
from django.contrib.sites.models import Site
from django.test import TestCase

from moses import errors
from moses.models import CustomUser
from moses.views.user import UserViewSet
from test_project.app_for_tests import APIClient
from test_project.app_for_tests import utils

test_client = APIClient('')


class PhoneNumberAndEmailConfirmationTestCase(TestCase):
    def setUp(self):
        self.confirm_phone_number_view = UserViewSet.as_view({'post': 'confirm_phone_number'})
        self.update_user_view = UserViewSet.as_view({'patch': 'me'})
        self.request_email_pin_view = UserViewSet.as_view({'patch': 'me'})
        self.request_phone_number_pin_view = UserViewSet.as_view({'post': 'request_phone_number_confirmation_pin'})
        self.enable_mfa_view = UserViewSet.as_view({'post': 'enable_mfa'})
        self.disable_mfa_view = UserViewSet.as_view({'post': 'disable_mfa'})
        self.get_mfa_key_veiew = UserViewSet.as_view({'get': 'get_mfa_key'})
        Site.objects.create(domain='wakamakafo.com')
        utils.SENT_SMS = {}

    def test_correct_pin_codes_came_after_register(self):
        self.user, response = test_client.create_user(
            phone_number='+996507030927',
            name='Q',
            password='secret!!1',
            email='fafa@gmail.com',
            domain='wakamakafo.com'
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(self.user.is_phone_number_confirmed)

        self.user, response = test_client.confirm_phone_number(self.user, utils.SENT_SMS['+996507030927'])
        self.assertTrue(self.user.is_phone_number_confirmed)
        self.assertEqual(self.user.phone_number_candidate, '')
        self.assertEqual(self.user.phone_number_candidate_confirmation_pin, 0)

        self.user, response = test_client.update_user(self.user, {'phone_number': '+996507030928'})
        self.assertEqual(CustomUser.objects.count(), 1)
        self.assertNotEqual(self.user.phone_number_candidate_confirmation_pin, 0)
        self.assertEqual(self.user.phone_number_candidate, '+996507030928')
        self.assertEqual(self.user.phone_number, '+996507030927')
        self.assertTrue(self.user.is_phone_number_confirmed, True)

        self.user, response = test_client.confirm_phone_number(
            self.user,
            utils.get_random_pin_non_equal_to(utils.SENT_SMS['+996507030927']),
            utils.get_random_pin_non_equal_to(utils.SENT_SMS['+996507030928'])
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data['pin'], [errors.INCORRECT_CONFIRMATION_PIN])
        self.assertEqual(response.data['candidate_pin'], [errors.INCORRECT_CONFIRMATION_PIN])
        self.user, response = test_client.confirm_phone_number(
            self.user,
            utils.get_random_pin_non_equal_to(utils.SENT_SMS['+996507030927']),
            utils.SENT_SMS['+996507030928']
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data['pin'], [errors.INCORRECT_CONFIRMATION_PIN])
        self.user, response = test_client.confirm_phone_number(
            self.user,
            utils.SENT_SMS['+996507030927'],
            utils.get_random_pin_non_equal_to(utils.SENT_SMS['+996507030928'])
        )
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['candidate_pin'], [errors.INCORRECT_CONFIRMATION_PIN])
        self.user, response = test_client.confirm_phone_number(
            self.user,
            utils.SENT_SMS['+996507030927'],
            utils.SENT_SMS['+996507030928']
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.phone_number, '+996507030928')
        self.assertEqual(self.user.phone_number_candidate, '')

        self.user, response = test_client.update_user(self.user, {'phone_number': '+996507030929'})
        self.assertEqual(self.user.phone_number, '+996507030928')
        self.assertEqual(self.user.phone_number_candidate, '+996507030929')

        self.user, response = test_client.update_user(self.user, {'phone_number': '+996507030930'})
        self.assertEqual(self.user.phone_number, '+996507030928')
        self.assertEqual(self.user.phone_number_candidate, '+996507030930')
        self.user, response = test_client.confirm_phone_number(
            self.user,
            utils.SENT_SMS['+996507030928'],
            utils.SENT_SMS['+996507030930']
        )

        self.assertTrue(self.user.is_phone_number_confirmed)
        self.assertEqual(self.user.phone_number, '+996507030930')
        self.assertEqual(self.user.phone_number_candidate, '')

        self.user, response = test_client.update_user(self.user, {'phone_number': '+996507030931'})
        self.assertEqual(self.user.phone_number, '+996507030930')
        self.assertEqual(self.user.phone_number_candidate, '+996507030931')
        self.assertTrue(self.user.is_phone_number_confirmed)
        first_pins = self.user.phone_number_confirmation_pin, self.user.phone_number_candidate_confirmation_pin
        del utils.SENT_SMS['+996507030930']
        del utils.SENT_SMS['+996507030931']
        self.assertNotIn('+996507030930', utils.SENT_SMS)
        self.assertNotIn('+996507030931', utils.SENT_SMS)
        self.user, response = test_client.request_phone_number_confirmation_pin(self.user)
        self.assertEqual(
            (self.user.phone_number_confirmation_pin, self.user.phone_number_candidate_confirmation_pin),
            first_pins)
        self.assertNotIn('+996507030930', utils.SENT_SMS)
        self.assertNotIn('+996507030931', utils.SENT_SMS)
        self.user.last_phone_number_confirmation_pins_sent -= timedelta(minutes=1)
        self.user.save()

        self.user, response = test_client.request_phone_number_confirmation_pin(self.user)
        self.assertEqual(
            (self.user.phone_number_confirmation_pin, self.user.phone_number_candidate_confirmation_pin),
            first_pins)
        self.assertIn('+996507030930', utils.SENT_SMS)
        self.assertIn('+996507030931', utils.SENT_SMS)
        random_key = utils.get_random_mfa_key()
        self.user, response = test_client.enable_mfa(
            self.user,
            random_key,
            pyotp.totp.TOTP(random_key.encode('utf-8')).now()
        )

        self.assertEqual(response.status_code, 200)

        self.user, response = test_client.disable_mfa(self.user, '')
        self.assertEqual(response.status_code, 401)
        self.assertNotEqual(self.user.mfa_secret_key, '')

        self.user, response = test_client.disable_mfa(self.user, pyotp.totp.TOTP(random_key).now())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.mfa_secret_key, '')
