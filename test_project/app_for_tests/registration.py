from django.test import TestCase
from rest_framework.test import APIRequestFactory

from moses.common import error_codes
from moses.models import CustomUser
from test_project.app_for_tests.confirmations import test_client

request_factory = APIRequestFactory()


class RegistrationTestCase(TestCase):
    fixtures = ['registration']

    def setUp(self):
        pass

    def test_can_register_on_existent_site(self):
        user, response = test_client.create_user(
            phone_number='+1',
            name='Q',
            password='secret!!1',
            email='bar@foo.com',
            domain='exists.com'
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(CustomUser.objects.last().is_phone_number_confirmed)

    def cant_register_if_phone_already_registered(self):
        user, response = test_client.create_user(
            phone_number='+0',
            name='Q',
            password='secret!!1',
            email='bar@foo.com',
            domain='exists.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors'][''][0]['error_code'], error_codes.EMAIL_ALREADY_REGISTERED_ON_DOMAIN)
        self.assertEqual(len(response.data), 1)

    def cant_register_if_email_already_registered(self):
        user, response = test_client.create_user(
            phone_number='+1',
            name='Q',
            password='secret!!1',
            email='foo@foo.com',
            domain='exists.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['non_field_errors'], error_codes.PHONE_NUMBER_ALREADY_REGISTERED_ON_DOMAIN)
        self.assertEqual(len(response.data), 1)

    def test_cant_register_on_non_existent_site(self):
        user, response = test_client.create_user(
            phone_number='+1',
            name='Q',
            password='secret!!1',
            email='bar@foo.com',
            domain='not.exists.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['domain'][0]['error_code'],
                         error_codes.SITE_WITH_DOMAIN_DOES_NOT_EXIST)

    def test_error_on_custom_phone_number_validator(self):
        user, response = test_client.create_user(
            phone_number='+10',
            name='Q',
            password='secret!!1',
            email='bar@foo.com',
            domain='exists.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['phone_number'][0]['error_code'], error_codes.INVALID_PHONE_NUMBER)

    def test_can_register_on_another_site_with_same_email_and_phone_number(self):
        user, response = test_client.create_user(
            phone_number='+0',
            name='Q',
            password='secret!!1',
            email='foo@foo.com',
            domain='exists2.com'
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CustomUser.objects.count(), 2)
