from django.test import TestCase

from moses import errors
from moses.models import CustomUser
from test_project.tests import APIClient
from test_project.tests.utils import SENT_SMS

test_client = APIClient('')


class ResetPasswordTestCase(TestCase):
    fixtures = ['reset_password']

    def setUp(self):
        self.user1 = CustomUser.objects.get(id=1)
        self.user2 = CustomUser.objects.get(id=2)

    def test_cannot_reset_password_on_non_existent_site(self):
        response = test_client.reset_password(
            '+0',
            'not.exists.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['domain'], [errors.SITE_WITH_DOMAIN_DOES_NOT_EXIST])
        self.assertEqual(len(response.data), 1)
        self.assertNotIn('+0', SENT_SMS)

    def test_cannot_reset_password_on_site_that_not_registered_on(self):
        response = test_client.reset_password(
            '+1',
            'exists.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['phone_number'], [errors.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN])
        self.assertEqual(len(response.data), 1)
        self.assertNotIn('+0', SENT_SMS)

    def test_can_reset_password_on_site_that_registered_on(self):
        response = test_client.reset_password(
            '+0',
            'exists.com'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('+0', SENT_SMS)

    def test_can_reset_password_on_site_that_registered_on(self):
        response = test_client.reset_password(
            '+0',
            'exists2.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['phone_number'], [errors.CREDENTIAL_NOT_CONFIRMED])
