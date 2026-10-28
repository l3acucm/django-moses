from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.test import TestCase, override_settings

from moses.common import error_codes
from test_project.app_for_tests import APIClient
from test_project.app_for_tests import utils

test_client = APIClient('')
User = get_user_model()

MOSES = {**settings.MOSES, "PHONE_OTP_LOGIN": True, "PHONE_OTP_REQUEST_IP_LIMIT": (3, 600)}
P1, P2, P3, P4 = ('+99650700000%d' % i for i in (1, 2, 3, 4))


def code(response):
    return response.data['errors'][''][0]['error_code']


@override_settings(MOSES=MOSES)
class OtpRequestTestCase(TestCase):
    def setUp(self):
        Site.objects.create(domain='a.com')
        Site.objects.create(domain='b.com')
        utils.SENT_SMS = {}
        utils.SENT_SMS_RAW = {}
        cache.clear()

    def test_new_number_gets_user_and_code(self):
        response = test_client.otp_request(P1, 'a.com')
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(phone_number=P1, site__domain='a.com')
        self.assertFalse(user.has_usable_password())
        self.assertNotEqual(user.phone_number_confirmation_pin, 0)
        self.assertEqual(utils.SENT_SMS[P1], user.phone_number_confirmation_pin)

    def test_existing_user_gets_new_code(self):
        user = User(phone_number=P1, site=Site.objects.get(domain='a.com'))
        user.set_unusable_password()
        user.save()
        response = test_client.otp_request(P1, 'a.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(phone_number=P1).count(), 1)
        user.refresh_from_db()
        self.assertEqual(utils.SENT_SMS[P1], user.phone_number_confirmation_pin)

    def test_second_request_inside_pause_is_too_frequent(self):
        self.assertEqual(test_client.otp_request(P1, 'a.com').status_code, 200)
        response = test_client.otp_request(P1, 'a.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(code(response), error_codes.TOO_FREQUENT_SMS_REQUESTS)
        self.assertEqual(User.objects.filter(phone_number=P1).count(), 1)

    def test_same_phone_two_sites_two_users(self):
        self.assertEqual(test_client.otp_request(P1, 'a.com').status_code, 200)
        self.assertEqual(test_client.otp_request(P1, 'b.com').status_code, 200)
        self.assertEqual(User.objects.filter(phone_number=P1).count(), 2)

    def test_ip_limit(self):
        for p in (P1, P2, P3):
            self.assertEqual(test_client.otp_request(p, 'a.com', ip='1.1.1.1').status_code, 200)
        response = test_client.otp_request(P4, 'a.com', ip='1.1.1.1')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(code(response), error_codes.TOO_FREQUENT_SMS_REQUESTS)
        self.assertEqual(test_client.otp_request(P4, 'a.com', ip='2.2.2.2').status_code, 200)

    def test_ip_header_is_used(self):
        from test_project.app_for_tests import drf_request_factory
        from moses.views.user import UserViewSet
        view = UserViewSet.as_view({'post': 'otp_request'})

        def call(phone, remote):
            request = drf_request_factory.post(
                '/', {'phone_number': phone, 'domain': 'a.com'}, format='json',
                REMOTE_ADDR=remote, HTTP_X_REAL_IP='9.9.9.9')
            return view(request).status_code

        with override_settings(MOSES={**MOSES, "IP_HEADER": "HTTP_X_REAL_IP"}):
            self.assertEqual([call(P1, '1.1.1.1'), call(P2, '2.2.2.2'), call(P3, '3.3.3.3')], [200] * 3)
            self.assertEqual(call(P4, '4.4.4.4'), 429)

    def test_default_has_no_ip_limit(self):
        with override_settings(MOSES={**settings.MOSES, "PHONE_OTP_LOGIN": True}):
            for i in range(5):
                response = test_client.otp_request('+99650700010%d' % i, 'a.com', ip='1.1.1.1')
                self.assertEqual(response.status_code, 200)


class OtpFlagOffTestCase(TestCase):
    def test_flag_off_is_404(self):
        Site.objects.create(domain='a.com')
        self.assertEqual(test_client.otp_request(P1, 'a.com').status_code, 404)
