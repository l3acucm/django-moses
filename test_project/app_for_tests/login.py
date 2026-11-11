from django.test import TestCase, override_settings

from moses.models import CustomUser
from test_project.app_for_tests import APIClient

test_client = APIClient('')


class LoginTestCase(TestCase):
    fixtures = ['login']
    def setUp(self):
        self.user1 = CustomUser.objects.get(id=1)
        self.user2 = CustomUser.objects.get(id=2)
        self.user1.set_password('abcxyz123')
        self.user2.set_password('abcxyz234')
        self.user1.save()
        self.user2.save()

    def test_can_login_on_proper_site(self):
        user, response = test_client.login(
            phone_number='+0',
            password='abcxyz123',
            domain='exists.com'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user1.id, user.id)
        user, response = test_client.login(
            phone_number='+0',
            password='abcxyz234',
            domain='exists2.com'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user2.id, user.id)

    def test_cant_login_on_wrong_site(self):
        user, response = test_client.login(
            phone_number='+0',
            password='abcxyz123',
            domain='exists2.com'
        )
        self.assertEqual(response.status_code, 401)


class LoginPhoneConfirmationGateTestCase(TestCase):
    """MOSES['REQUIRE_PHONE_NUMBER_CONFIRMATION_FOR_LOGIN'] (default True)
    blocks login for a correct password on an unconfirmed phone number."""
    fixtures = ['login']

    def setUp(self):
        self.user1 = CustomUser.objects.get(id=1)
        self.user1.set_password('abcxyz123')
        self.user1.is_phone_number_confirmed = False
        self.user1.save()

    def test_blocks_login_by_default_when_phone_not_confirmed(self):
        user, response = test_client.login(
            phone_number='+0', password='abcxyz123', domain='exists.com')
        self.assertEqual(response.status_code, 401)
        self.assertIsNone(user)
        self.assertEqual(
            response.data['errors'][''][0]['error_code'], 'phone_number_not_confirmed')

    @override_settings(MOSES={'REQUIRE_PHONE_NUMBER_CONFIRMATION_FOR_LOGIN': False})
    def test_allows_login_when_setting_disabled(self):
        user, response = test_client.login(
            phone_number='+0', password='abcxyz123', domain='exists.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user1.id, user.id)
