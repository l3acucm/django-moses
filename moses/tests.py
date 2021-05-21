import re
from datetime import datetime, timedelta

import factory
import mock
from django.test import TestCase
from django.urls import reverse, resolve
from factory.django import DjangoModelFactory
from rest_framework.test import force_authenticate, APIRequestFactory

from project.accounts.models import CustomUser
from project.accounts.views import ConfirmPhoneNumber, RequestEmailConfirmPin, RequestPhoneNumberConfirmPin

request_factory = APIRequestFactory()

SENT_SMS = {}


def alarm(to, body):
    SENT_SMS[to] = re.findall('\d+', body)[0]


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
        self.update_user_view = resolve(reverse('api:accounts:customuser-me')).func
        self.request_email_pin_view = RequestEmailConfirmPin.as_view()
        self.request_phone_number_pin_view = RequestPhoneNumberConfirmPin.as_view()

    @mock.patch("project.common.sms.send", alarm)
    def test_correct_pin_codes_came_after_register(self):
        data = {'phone_number': '+996507030927', 'first_name': 'Q2', 'last_name': 'Q3',
                'password': 'secret!!1', 'inviter_id': CustomUser.objects.first().id, 'email': 'fafa@gmail.com'}
        self.client.post(reverse('api:accounts:customuser-list'), data)
        self.assertFalse(CustomUser.objects.last().is_phone_number_confirmed)

        request = request_factory.post(reverse('api:accounts:confirm_phone_number'),
                                       {'pin': SENT_SMS['+996507030927'][:-1]})
        force_authenticate(request, user=CustomUser.objects.last())
        self.confirm_phone_number_view(request)

        self.assertFalse(CustomUser.objects.last().is_phone_number_confirmed)
        request = request_factory.post(reverse('api:accounts:confirm_phone_number'), {'pin': SENT_SMS['+996507030927']})
        force_authenticate(request, user=CustomUser.objects.last())
        self.confirm_phone_number_view(request)
        self.assertTrue(CustomUser.objects.last().is_phone_number_confirmed)

        request = request_factory.patch(reverse('api:accounts:customuser-me'), {'phone_number': '+996507030928'})
        force_authenticate(request, user=CustomUser.objects.last())
        self.update_user_view(request)

        self.assertEqual(request.user.phone_number_candidate, '+996507030928')
        self.assertEqual(request.user.phone_number, '+996507030927')
        self.assertTrue(request.user.is_phone_number_confirmed, True)

        request = request_factory.post(reverse('api:accounts:confirm_phone_number'),
                                       {'pin': SENT_SMS['+996507030927'], 'candidatePin': SENT_SMS['+996507030928']})
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.confirm_phone_number_view(request)
        self.assertEqual(request.user.phone_number, '+996507030928')
        self.assertEqual(request.user.phone_number_candidate, '')

        request = request_factory.patch(reverse('api:accounts:customuser-me'), {'phone_number': '+996507030929'})
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.update_user_view(request)
        self.assertEqual(request.user.phone_number, '+996507030928')
        self.assertEqual(request.user.phone_number_candidate, '+996507030929')

        request = request_factory.patch(reverse('api:accounts:customuser-me'), {'phone_number': '+996507030930'})
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.update_user_view(request)
        self.assertEqual(request.user.phone_number, '+996507030928')
        self.assertEqual(request.user.phone_number_candidate, '+996507030930')

        request = request_factory.post(reverse('api:accounts:confirm_phone_number'),
                                       {'pin': SENT_SMS['+996507030928'][:-1],
                                        'candidatePin': SENT_SMS['+996507030930']})
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.confirm_phone_number_view(request)
        self.assertEqual(request.user.phone_number, '+996507030928')
        self.assertEqual(request.user.phone_number_candidate, '+996507030930')
        self.assertTrue(request.user.is_phone_number_confirmed)

        request = request_factory.post(reverse('api:accounts:confirm_phone_number'),
                                       {'pin': SENT_SMS['+996507030928'], 'candidatePin': SENT_SMS['+996507030930']})
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.confirm_phone_number_view(request)
        self.assertEqual(request.user.phone_number, '+996507030930')
        self.assertTrue(request.user.is_phone_number_confirmed)
        self.assertEqual(request.user.phone_number_candidate, '')

        request = request_factory.patch(reverse('api:accounts:customuser-me'), {'phone_number': '+996507030931'})
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.update_user_view(request)
        self.assertEqual(request.user.phone_number, '+996507030930')
        self.assertEqual(request.user.phone_number_candidate, '+996507030931')
        self.assertTrue(request.user.is_phone_number_confirmed)

        first_pins = request.user.phone_number_confirm_pin, request.user.phone_number_candidate_confirm_pin
        del SENT_SMS['+996507030930']
        del SENT_SMS['+996507030931']
        self.assertNotIn('+996507030930', SENT_SMS)
        self.assertNotIn('+996507030931', SENT_SMS)
        request = request_factory.post(reverse('api:accounts:request_phone_number_confirm_pin'))
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.request_phone_number_pin_view(request)
        self.assertEqual((request.user.phone_number_confirm_pin, request.user.phone_number_candidate_confirm_pin),
                         first_pins)
        self.assertNotIn('+996507030930', SENT_SMS)
        self.assertNotIn('+996507030931', SENT_SMS)
        request.user.last_phone_number_confirm_pin_sent -= timedelta(days=1)
        request.user.last_phone_number_candidate_confirm_pin_sent -= timedelta(days=1)
        request.user.save()

        request = request_factory.post(reverse('api:accounts:request_phone_number_confirm_pin'))
        force_authenticate(request, user=CustomUser.objects.last())
        response = self.request_phone_number_pin_view(request)
        self.assertEqual((request.user.phone_number_confirm_pin, request.user.phone_number_candidate_confirm_pin),
                         first_pins)
        self.assertIn('+996507030930', SENT_SMS)
        self.assertIn('+996507030931', SENT_SMS)
