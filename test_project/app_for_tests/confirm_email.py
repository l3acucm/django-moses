from django.test import TestCase

from moses import errors
from moses.models import CustomUser
from test_project.app_for_tests import APIClient
from test_project.app_for_tests.utils import get_random_pin_non_equal_to

test_client = APIClient('')


class LoginTestCase(TestCase):
    fixtures = ['confirm_email']

    def setUp(self):
        self.user1 = CustomUser.objects.get(id=1)
        self.user2 = CustomUser.objects.get(id=2)
        self.user3 = CustomUser.objects.get(id=3)

    def test_need_to_confirm_only_candidate_if_main_email_is_not_confirmed(self):
        self.user1, response = test_client.confirm_email(
            self.user1,
            None,
            get_random_pin_non_equal_to(self.user1.email_candidate_confirmation_pin)
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data['candidate_pin'], [errors.INCORRECT_CONFIRMATION_PIN])
        self.assertEqual(self.user1.email_candidate, 'bar@foo.com')
        self.assertEqual(self.user1.email, 'foo@foo.com')
        self.assertFalse(self.user1.is_email_confirmed)
        self.user1, response = test_client.confirm_email(
            self.user1,
            None,
            self.user1.email_candidate_confirmation_pin
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user1.email_candidate, '')
        self.assertEqual(self.user1.email, 'bar@foo.com')
        self.assertTrue(self.user1.is_email_confirmed)

    def test_need_to_confirm_both_candidate_and_main_if_main_email_is_confirmed(self):
        self.user2, response = test_client.confirm_email(
            self.user2,
            None,
            get_random_pin_non_equal_to(self.user2.email_candidate_confirmation_pin)
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data['pin'], [errors.INCORRECT_CONFIRMATION_PIN])
        self.assertEqual(response.data['candidate_pin'], [errors.INCORRECT_CONFIRMATION_PIN])
        self.assertEqual(self.user2.email_candidate, 'bar@foo.com')
        self.assertEqual(self.user2.email, 'foo@foo.com')
        self.assertTrue(self.user2.is_email_confirmed)
        self.user2, response = test_client.confirm_email(
            self.user2,
            get_random_pin_non_equal_to(self.user2.email_confirmation_pin),
            self.user2.email_candidate_confirmation_pin
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data['pin'], [errors.INCORRECT_CONFIRMATION_PIN])
        self.assertEqual(self.user2.email_candidate, 'bar@foo.com')
        self.assertEqual(self.user2.email, 'foo@foo.com')
        self.assertTrue(self.user2.is_email_confirmed)
        self.user2, response = test_client.confirm_email(
            self.user2,
            self.user2.email_confirmation_pin,
            self.user2.email_candidate_confirmation_pin
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user2.email_candidate, '')
        self.assertEqual(self.user2.email, 'bar@foo.com')
        self.assertTrue(self.user2.is_email_confirmed)