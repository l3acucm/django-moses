import base64
import random
import re
import string
from datetime import timedelta

import pyotp
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import force_authenticate, APIRequestFactory

from moses.models import CustomUser

request_factory = APIRequestFactory()

SENT_SMS = {}


def remember_pin(to, body):
    SENT_SMS[to] = re.findall(r'\d+', body)[0]


class RegistrationTestCase(TestCase):
    fixtures = ['registration']

    def setUp(self):
        pass

    def test_can_register_on_existent_site(self):
        data = {
            'phone_number': '+996507030927',
            'first_name': 'Q2',
            'last_name': 'Q3',
            'password': 'secret!!1',
            'email': 'fafa@gmail.com',
            'domain': 'exists.com'
        }
        response = self.client.post(reverse('moses:customuser-list'), data)
        self.assertEqual(response.status_code, 201)
        self.assertFalse(CustomUser.objects.last().is_phone_number_confirmed)
        response = self.client.post(reverse('moses:customuser-list'), data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['non_field_errors'], ['email_already_registered'])
        data['email'] += 'm'
        response = self.client.post(reverse('moses:customuser-list'), data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['non_field_errors'], ['phone_number_already_registered'])

    def test_cant_register_on_non_existent_site(self):
        data = {
            'phone_number': '+996507030927',
            'first_name': 'Q2',
            'last_name': 'Q3',
            'password': 'secret!!1',
            'email': 'fafa@gmail.com',
            'domain': 'not.exists.com'
        }
        response = self.client.post(reverse('moses:customuser-list'), data)
        self.assertEqual(response.status_code, 400)

