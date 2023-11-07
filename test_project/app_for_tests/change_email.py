from django.test import TestCase

from moses.models import CustomUser
from test_project.app_for_tests import APIClient

test_client = APIClient('')


class LoginTestCase(TestCase):
    fixtures = ['change_email']

    def setUp(self):
        self.user1 = CustomUser.objects.get(id=1)
        self.user2 = CustomUser.objects.get(id=2)

    def test_new_email_becomes_current_if_current_is_not_confirmed(self):
        self.user1, response = test_client.update_user(
            self.user1,
            {'email': 'bar@foo.com'}
        )
        self.assertEqual(self.user1.email_candidate, '')
        self.assertEqual(self.user1.email, 'bar@foo.com')
        self.assertFalse(self.user1.is_email_confirmed)

    def test_new_email_becomes_candidate_if_current_is_confirmed(self):
        self.user2, response = test_client.update_user(
            self.user2,
            {'email': 'bar@foo.com'}
        )
        self.assertEqual(self.user2.email_candidate, 'bar@foo.com')
        self.assertEqual(self.user2.email, 'foo@foo.com')
        self.assertTrue(self.user2.is_email_confirmed)
