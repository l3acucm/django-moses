import base64
import random
import re
import string
from datetime import datetime, timedelta

import factory
import pyotp
from django.contrib.auth.models import Group
from factory.django import DjangoModelFactory

from django.test import TestCase
from django.urls import reverse, resolve

from rest_framework.test import force_authenticate, APIRequestFactory

from moses.models import CustomUser
from moses.views import ConfirmPhoneNumber, RequestEmailConfirmPin, RequestPhoneNumberConfirmPin, MFAView, GetUserRoles

request_factory = APIRequestFactory()

SENT_SMS = {}


def remember_pin(to, body):
    SENT_SMS[to] = re.findall(r'\d+', body)[0]


class CustomUserFactory(DjangoModelFactory):
    class Meta:
        model = CustomUser

    phone_number = factory.Faker('phone_number')
    first_name = factory.Faker('first_name')
    email = factory.Faker('email')
    last_phone_number_candidate_confirm_pin_sent = factory.LazyFunction(datetime.now)
    last_phone_number_confirm_pin_sent = factory.LazyFunction(datetime.now)


class RegisterTestCase(TestCase):
    def setUp(self):
        self.confirm_phone_number_view = ConfirmPhoneNumber.as_view()
        self.update_user_view = resolve(reverse('moses:customuser-me')).func
        self.request_email_pin_view = RequestEmailConfirmPin.as_view()
        self.request_phone_number_pin_view = RequestPhoneNumberConfirmPin.as_view()
        self.mfa_view = MFAView.as_view()

    def test_correct_pin_codes_came_after_register(self):
        data = {
            'phone_number': '+996507030927',
            'first_name': 'Q2',
            'last_name': 'Q3',
            'password': 'secret!!1',
            'email': 'fafa@gmail.com'
        }
        response = self.client.post(reverse('moses:customuser-list'), data)
        self.assertEqual(response.status_code, 201)
        self.assertFalse(CustomUser.objects.last().is_phone_number_confirmed)

        request = request_factory.post(reverse('moses:confirm_phone_number'),
                                       {'pin': SENT_SMS['+996507030927'][:-1]})
        force_authenticate(request, user=CustomUser.objects.last())
        self.confirm_phone_number_view(request)

        self.assertFalse(CustomUser.objects.last().is_phone_number_confirmed)
        request = request_factory.post(reverse('moses:confirm_phone_number'), {'pin': SENT_SMS['+996507030927']})
        force_authenticate(request, user=CustomUser.objects.last())
        self.confirm_phone_number_view(request)
        self.assertTrue(CustomUser.objects.last().is_phone_number_confirmed)
        self.assertEqual(CustomUser.objects.last().phone_number_candidate, '')
        self.assertEqual(CustomUser.objects.last().phone_number_candidate_confirm_pin, 0)

        request = request_factory.patch(reverse('moses:customuser-me'), {'phone_number': '+996507030928'})
        force_authenticate(request, user=CustomUser.objects.last())
        self.update_user_view(request)

        self.assertEqual(CustomUser.objects.count(), 1)
        self.assertNotEqual(CustomUser.objects.last().phone_number_candidate_confirm_pin, 0)
        self.assertEqual(CustomUser.objects.last().phone_number_candidate, '+996507030928')
        self.assertEqual(CustomUser.objects.last().phone_number, '+996507030927')
        self.assertTrue(CustomUser.objects.last().is_phone_number_confirmed, True)

        request = request_factory.post(reverse('moses:confirm_phone_number'),
                                       {'pin': SENT_SMS['+996507030927'], 'candidate_pin': SENT_SMS['+996507030928']})
        force_authenticate(request, user=CustomUser.objects.last())
        self.confirm_phone_number_view(request)
        self.assertEqual(CustomUser.objects.last().phone_number, '+996507030928')
        self.assertEqual(CustomUser.objects.last().phone_number_candidate, '')

        request = request_factory.patch(reverse('moses:customuser-me'), {'phone_number': '+996507030929'})
        force_authenticate(request, user=CustomUser.objects.last())
        self.update_user_view(request)
        self.assertEqual(CustomUser.objects.last().phone_number, '+996507030928')
        self.assertEqual(CustomUser.objects.last().phone_number_candidate, '+996507030929')

        request = request_factory.patch(reverse('moses:customuser-me'), {'phone_number': '+996507030930'})
        force_authenticate(request, user=CustomUser.objects.last())
        self.update_user_view(request)
        self.assertEqual(CustomUser.objects.last().phone_number, '+996507030928')
        self.assertEqual(CustomUser.objects.last().phone_number_candidate, '+996507030930')

        request = request_factory.post(reverse('moses:confirm_phone_number'),
                                       {'pin': SENT_SMS['+996507030928'][:-1],
                                        'candidate_pin': SENT_SMS['+996507030930']})
        force_authenticate(request, user=CustomUser.objects.last())
        self.confirm_phone_number_view(request)
        self.assertEqual(CustomUser.objects.last().phone_number, '+996507030928')
        self.assertEqual(CustomUser.objects.last().phone_number_candidate, '+996507030930')
        self.assertTrue(CustomUser.objects.last().is_phone_number_confirmed)

        request = request_factory.post(reverse('moses:confirm_phone_number'),
                                       {'pin': SENT_SMS['+996507030928'], 'candidate_pin': SENT_SMS['+996507030930']})
        force_authenticate(request, user=CustomUser.objects.last())
        self.confirm_phone_number_view(request)
        self.assertEqual(CustomUser.objects.last().phone_number, '+996507030930')
        self.assertTrue(CustomUser.objects.last().is_phone_number_confirmed)
        self.assertEqual(CustomUser.objects.last().phone_number_candidate, '')

        request = request_factory.patch(reverse('moses:customuser-me'), {'phone_number': '+996507030931'})
        force_authenticate(request, user=CustomUser.objects.last())
        self.update_user_view(request)
        self.assertEqual(CustomUser.objects.last().phone_number, '+996507030930')
        self.assertEqual(CustomUser.objects.last().phone_number_candidate, '+996507030931')
        self.assertTrue(CustomUser.objects.last().is_phone_number_confirmed)

        first_pins = request.user.phone_number_confirm_pin, request.user.phone_number_candidate_confirm_pin
        del SENT_SMS['+996507030930']
        del SENT_SMS['+996507030931']
        self.assertNotIn('+996507030930', SENT_SMS)
        self.assertNotIn('+996507030931', SENT_SMS)
        request = request_factory.post(reverse('moses:request_phone_number_confirm_pin'))
        force_authenticate(request, user=CustomUser.objects.last())
        self.request_phone_number_pin_view(request)
        self.assertEqual((CustomUser.objects.last().phone_number_confirm_pin, request.user.phone_number_candidate_confirm_pin),
                         first_pins)
        self.assertNotIn('+996507030930', SENT_SMS)
        self.assertNotIn('+996507030931', SENT_SMS)
        request.user.last_phone_number_confirm_pin_sent -= timedelta(days=1)
        request.user.last_phone_number_candidate_confirm_pin_sent -= timedelta(days=1)
        request.user.save()

        request = request_factory.post(reverse('moses:request_phone_number_confirm_pin'))
        force_authenticate(request, user=CustomUser.objects.last())
        self.request_phone_number_pin_view(request)
        self.assertEqual(
            (CustomUser.objects.last().phone_number_confirm_pin, request.user.phone_number_candidate_confirm_pin),
            first_pins)
        self.assertIn('+996507030930', SENT_SMS)
        self.assertIn('+996507030931', SENT_SMS)
        random_key = base64.b32encode(
                bytes(''.join(random.choice(string.ascii_letters) for _ in range(16)).encode('utf-8'))).decode('utf-8')
        request = request_factory.post(reverse('moses:mfa'),
                                        {'action': 'enable', 'mfa_secret_key': random_key, 'otp': pyotp.totp.TOTP(random_key.encode('utf-8')).now()})

        force_authenticate(request, user=CustomUser.objects.last())
        response = self.mfa_view(request)

        self.assertEqual(response.status_code, 200)

        request = request_factory.post(reverse('moses:mfa'), {'action': 'disable'})
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.mfa_view(request)
        self.assertEqual(response.status_code, 401)

        request = request_factory.post(reverse('moses:mfa'), {'action': 'disable'})
        request.META['HTTP_OTP'] = pyotp.totp.TOTP(random_key.encode('utf-8')).now()
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.mfa_view(request)
        self.assertEqual(response.status_code, 200)


class UserRolesTestCase(TestCase):
    fixtures = ["fixtures/tests/get_user_roles_test_case"]

    def setUp(self):
        self.request_user_roles_view = GetUserRoles.as_view()
        self.user = CustomUser.objects.first()
        self.group = Group.objects.first()
        self.missing_group = Group.objects.last()
        self.user.groups.add(self.group.id)

    def test_get_user_roles(self):
        request = request_factory.get(reverse('moses:user_roles'))
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.request_user_roles_view(request)
        self.assertTrue(response.data.filter(id=self.group.id))
        self.assertFalse(response.data.filter(id=self.missing_group.id))
