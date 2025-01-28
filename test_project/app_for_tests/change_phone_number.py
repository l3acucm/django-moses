from django.test import TestCase
from rest_framework import status

from moses.models import CustomUser
from test_project.app_for_tests import APIClient

test_client = APIClient('')


class ChangePhoneNumberTestCase(TestCase):
    fixtures = ['change_phone_number']

    def setUp(self):
        self.user1 = CustomUser.objects.get(id=1)
        self.user2 = CustomUser.objects.get(id=2)

    def test_new_phone_number_becomes_current_if_current_is_not_confirmed(self):
        self.user1, response = test_client.update_user(
            self.user1,
            {'phone_number': '+3'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.user1.phone_number_candidate, '')
        self.assertEqual(self.user1.phone_number, '+3')
        self.assertFalse(self.user1.is_phone_number_confirmed)

    def test_new_phone_number_becomes_candidate_if_current_is_confirmed(self):
        self.user2, response = test_client.update_user(
            self.user2,
            {'phone_number': '+3'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.user2.phone_number_candidate, '+3')
        self.assertEqual(self.user2.phone_number, '+0')
        self.assertTrue(self.user2.is_phone_number_confirmed)
