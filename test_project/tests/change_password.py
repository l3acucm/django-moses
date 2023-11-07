from django.test import TestCase

from moses import errors
from moses.models import CustomUser
from test_project.tests import APIClient

test_client = APIClient('')


class ChangePasswordTestCase(TestCase):
    fixtures = ['change_password']

    def setUp(self):
        self.user1 = CustomUser.objects.get(id=1)
        self.user2 = CustomUser.objects.get(id=2)
        self.user1.set_password('abcxyz123')
        self.user2.set_password('abcxyz234')
        self.user1.save()
        self.user2.save()

    def test_password_change_affects_only_one_site(self):
        user, response = test_client.update_password(
            self.user1,
            'abcxyz223',
            'abcxyz345'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['current_password'], [errors.INVALID_PASSWORD])
        self.assertEqual(len(response.data), 1)
        user, response = test_client.update_password(
            self.user1,
            'abcxyz123',
            'abcxyz345'
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.user1.id, user.id)
        user, response = test_client.login(
            phone_number='+0',
            password='abcxyz345',
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
