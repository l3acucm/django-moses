from django.test import TestCase

from moses.models import CustomUser
from test_project.tests import APIClient

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
