from django.test import TestCase

from moses import errors
from moses.models import CustomUser
from test_project.app_for_tests import APIClient, utils

test_client = APIClient('')


class ResetPasswordTestCase(TestCase):
    fixtures = ['reset_password']

    def setUp(self):
        self.user1 = CustomUser.objects.get(id=1)
        self.user2 = CustomUser.objects.get(id=2)
        utils.SENT_SMS = {}

    def test_cannot_reset_password_on_non_existent_site(self):
        response = test_client.reset_password(
            '+0',
            'not.exists.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['credential'],
                         [errors.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN])
        self.assertEqual(len(response.data), 1)
        self.assertNotIn('+0', utils.SENT_SMS)

    def test_cannot_reset_password_on_site_that_not_registered_on(self):
        response = test_client.reset_password(
            '+1',
            'exists.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['credential'],
                         [errors.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN])
        self.assertEqual(len(response.data), 1)
        self.assertNotIn('+0', utils.SENT_SMS)

    def test_can_reset_password_on_site_that_registered_on(self):
        response = test_client.reset_password(
            '+0',
            'exists.com'
        )
        self.assertEqual(response.status_code, 204)
        self.assertIn('+0', utils.SENT_SMS)
        self.assertFalse(self.user1.check_password('123123123'))
        self.user1, response = test_client.confirm_reset_password('+0', 'exists2.com', 'bad_code', '123123123')
        if self.user1 is None:
            self.user1 = CustomUser.objects.get(id=1)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.user1.check_password('123123123'))
        self.user1, response = test_client.confirm_reset_password('+0', 'exists2.com', utils.SENT_SMS['+0'],
                                                                  '123123123')
        if self.user1 is None:
            self.user1 = CustomUser.objects.get(id=1)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.user1.check_password('123123123'))
        self.user1, response = test_client.confirm_reset_password('+0', 'exists.com', 'bad_code', '123123123')
        if self.user1 is None:
            self.user1 = CustomUser.objects.get(id=1)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.user1.check_password('123123123'))
        self.user1, response = test_client.confirm_reset_password('+0', 'exists.com', utils.SENT_SMS['+0'], '123123123')
        if self.user1 is None:
            self.user1 = CustomUser.objects.get(id=1)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(self.user1.check_password('123123123'))

    def test_cannot_reset_password_on_site_that_is_not_registered_on(self):
        response = test_client.reset_password(
            '+0',
            'exists2.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['credential'],
                         [errors.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN])
