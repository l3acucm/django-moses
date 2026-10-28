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
        with override_settings(MOSES={k: v for k, v in MOSES.items() if k != "PHONE_OTP_REQUEST_IP_LIMIT"}):
            for i in range(5):
                response = test_client.otp_request('+99650700010%d' % i, 'a.com', ip='1.1.1.1')
                self.assertEqual(response.status_code, 200)


class OtpFlagOffTestCase(TestCase):
    def test_flag_off_is_404(self):
        Site.objects.create(domain='a.com')
        self.assertEqual(test_client.otp_request(P1, 'a.com').status_code, 404)


@override_settings(MOSES=MOSES)
class OtpVerifyTestCase(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain='a.com')
        utils.SENT_SMS = {}
        utils.SENT_SMS_RAW = {}
        cache.clear()
        self.received = []
        from moses.signals import phone_number_confirmed
        self.signal = phone_number_confirmed
        self.signal.connect(self._receiver)
        self.addCleanup(self.signal.disconnect, self._receiver)

    def _receiver(self, sender, **kwargs):
        self.received.append(kwargs)

    def request_code(self, phone=P1):
        self.assertEqual(test_client.otp_request(phone, 'a.com').status_code, 200)
        return utils.SENT_SMS[phone]

    def test_right_code_returns_tokens_and_confirms(self):
        pin = self.request_code()
        response = test_client.otp_verify(P1, str(pin), 'a.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {'access', 'refresh'})
        user = User.objects.get(phone_number=P1)
        self.assertTrue(user.is_phone_number_confirmed)
        self.assertEqual(user.phone_number_confirmation_pin, 0)
        self.assertEqual(len(self.received), 1)
        self.assertTrue(self.received[0]['is_initial_confirmation'])
        self.assertEqual(self.received[0]['user'].pk, user.pk)

    def test_code_works_once(self):
        pin = self.request_code()
        self.assertEqual(test_client.otp_verify(P1, str(pin), 'a.com').status_code, 200)
        response = test_client.otp_verify(P1, str(pin), 'a.com')
        self.assertEqual(response.status_code, 400)
        self.assertIn('code', response.data['errors'])

    def test_wrong_code_counts_attempts_then_limit(self):
        pin = self.request_code()
        wrong = str(pin + 1 if pin < 999999 else pin - 1)
        for _ in range(4):
            response = test_client.otp_verify(P1, wrong, 'a.com')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data['errors']['code'][0]['error_code'],
                             error_codes.INCORRECT_CONFIRMATION_PIN)
        response = test_client.otp_verify(P1, str(pin), 'a.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(code(response), error_codes.ATTEMPTS_LIMIT_REACHED)

    def test_new_code_resets_attempts(self):
        pin = self.request_code()
        wrong = str(pin + 1 if pin < 999999 else pin - 1)
        for _ in range(4):
            test_client.otp_verify(P1, wrong, 'a.com')
        User.objects.filter(phone_number=P1).update(phone_number_confirmation_code_sms_unlocks_at=None)
        new_pin = self.request_code()
        self.assertEqual(test_client.otp_verify(P1, str(new_pin), 'a.com').status_code, 200)

    def test_zero_or_empty_code_never_matches(self):
        user = User(phone_number=P1, site=self.site)
        user.set_unusable_password()
        user.save()
        self.assertEqual(user.phone_number_confirmation_pin, 0)
        for c in ('', '0'):
            self.assertEqual(test_client.otp_verify(P1, c, 'a.com').status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.is_phone_number_confirmed)

    def test_unknown_number_looks_like_wrong_code(self):
        response = test_client.otp_verify(P2, '123456', 'a.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['code'][0]['error_code'],
                         error_codes.INCORRECT_CONFIRMATION_PIN)

    def test_candidate_change_untouched(self):
        pin = self.request_code()
        User.objects.filter(phone_number=P1).update(
            phone_number_candidate='+996507000999', phone_number_candidate_confirmation_pin=111111)
        self.assertEqual(test_client.otp_verify(P1, str(pin), 'a.com').status_code, 200)
        user = User.objects.get(phone_number=P1)
        self.assertEqual(user.phone_number_candidate, '+996507000999')
        self.assertEqual(user.phone_number_candidate_confirmation_pin, 111111)

    def test_already_confirmed_user_no_signal(self):
        pin = self.request_code()
        User.objects.filter(phone_number=P1).update(is_phone_number_confirmed=True)
        self.assertEqual(test_client.otp_verify(P1, str(pin), 'a.com').status_code, 200)
        self.assertEqual(self.received, [])

    def test_stale_user_object_does_not_clobber_concurrent_changes(self):
        from moses.services.otp_login import verify_login_code
        pin = self.request_code()
        stale = User.objects.get(phone_number=P1)
        User.objects.filter(phone_number=P1).update(
            phone_number_candidate='+996507000999', phone_number_candidate_confirmation_pin=111111)
        self.assertTrue(verify_login_code(stale, str(pin)))
        user = User.objects.get(phone_number=P1)
        self.assertEqual(user.phone_number_candidate, '+996507000999')
        self.assertEqual(user.phone_number_candidate_confirmation_pin, 111111)
        self.assertTrue(user.is_phone_number_confirmed)

    def test_attempts_are_read_from_db_not_stale_object(self):
        from moses.common.exceptions import CustomAPIException
        from moses.services.otp_login import verify_login_code
        pin = self.request_code()
        stale = User.objects.get(phone_number=P1)
        User.objects.filter(phone_number=P1).update(phone_number_confirmation_attempts=4)
        with self.assertRaises(CustomAPIException):
            verify_login_code(stale, str(pin))
        # a stale object must not let a used code succeed again
        User.objects.filter(phone_number=P1).update(
            phone_number_confirmation_attempts=0, phone_number_confirmation_pin=0)
        self.assertFalse(verify_login_code(stale, str(pin)))

    def test_inactive_user_gets_wrong_code(self):
        pin = self.request_code()
        User.objects.filter(phone_number=P1).update(is_active=False)
        response = test_client.otp_verify(P1, str(pin), 'a.com')
        self.assertEqual(response.status_code, 400)
        self.assertIn('code', response.data['errors'])


class OtpVerifyFlagOffTestCase(TestCase):
    def test_flag_off_is_404(self):
        Site.objects.create(domain='a.com')
        self.assertEqual(test_client.otp_verify(P1, '123456', 'a.com').status_code, 404)
