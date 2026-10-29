from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings

from moses.common import error_codes
from test_project.app_for_tests import APIClient
from test_project.app_for_tests import utils

test_client = APIClient('')
User = get_user_model()

MOSES = {**settings.MOSES, "LOGIN_METHODS": ["WITHOUT_PASSWORD"], "PHONE_OTP_REQUEST_IP_LIMIT": (3, 600)}
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

    def test_inactive_user_gets_nothing_sent(self):
        user = User(phone_number=P1, site=Site.objects.get(domain='a.com'), is_active=False)
        user.set_unusable_password()
        user.save()
        response = test_client.otp_request(P1, 'a.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {})
        self.assertEqual(utils.SENT_SMS, {})
        user.refresh_from_db()
        self.assertEqual(user.phone_number_confirmation_pin, 0)

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

    def test_invalid_phone_number(self):
        response = test_client.otp_request('+99650', 'a.com')  # the test validator rejects it
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['phone_number'][0]['error_code'],
                         error_codes.INVALID_PHONE_NUMBER)
        self.assertFalse(User.objects.exists())
        self.assertEqual(utils.SENT_SMS, {})

    def assert_invalid_phone(self, phone, moses=MOSES):
        cache.clear()  # keep the per-IP limit out of the way
        with override_settings(MOSES=moses):
            response = test_client.otp_request(phone, 'a.com')
        self.assertEqual(response.status_code, 400, phone)
        self.assertEqual(response.data['errors']['phone_number'][0]['error_code'],
                         error_codes.INVALID_PHONE_NUMBER)

    def test_blank_or_too_long_phone_is_invalid_even_without_validator(self):
        no_validator = {**MOSES, "PHONE_NUMBER_VALIDATOR": None}
        for phone in ('', '+' + '9' * 20):
            self.assert_invalid_phone(phone)
            self.assert_invalid_phone(phone, no_validator)
        self.assertFalse(User.objects.exists())

    def test_non_string_inputs_are_400(self):
        for phone in (996507000001, ['+996507000001'], {'a': 1}, None):
            self.assert_invalid_phone(phone)
        for domain in (1, ['a.com'], {'a': 1}):
            cache.clear()
            response = test_client.otp_request(P1, domain)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data['errors']['domain'][0]['error_code'],
                             error_codes.SITE_WITH_DOMAIN_DOES_NOT_EXIST)
        self.assertFalse(User.objects.exists())

    def test_unknown_domain(self):
        response = test_client.otp_request(P1, 'nope.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['domain'][0]['error_code'],
                         error_codes.SITE_WITH_DOMAIN_DOES_NOT_EXIST)
        self.assertFalse(User.objects.exists())
        self.assertEqual(utils.SENT_SMS, {})

    def test_default_has_no_ip_limit(self):
        with override_settings(MOSES={k: v for k, v in MOSES.items() if k != "PHONE_OTP_REQUEST_IP_LIMIT"}):
            for i in range(5):
                response = test_client.otp_request('+99650700010%d' % i, 'a.com', ip='1.1.1.1')
                self.assertEqual(response.status_code, 200)


@override_settings(MOSES=MOSES)
class OtpRequestRaceTestCase(TransactionTestCase):
    def test_parallel_first_request_reuses_the_committed_row(self):
        import threading
        from django.db import connection
        from django.db.models.signals import pre_save
        site = Site.objects.create(domain='a.com')
        utils.SENT_SMS = {}
        cache.clear()
        fired = []

        def insert_from_another_connection():
            other = User(phone_number=P1, site=site)
            other.set_unusable_password()
            other.save()
            connection.close()

        def competing_insert(sender, instance, **kwargs):
            if instance._state.adding and not fired:
                fired.append(1)
                thread = threading.Thread(target=insert_from_another_connection)
                thread.start()
                thread.join()

        pre_save.connect(competing_insert, sender=User)
        self.addCleanup(pre_save.disconnect, competing_insert, sender=User)
        response = test_client.otp_request(P1, 'a.com')
        self.assertEqual(fired, [1])
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(phone_number=P1)
        self.assertEqual(utils.SENT_SMS[P1], user.phone_number_confirmation_pin)


class CountHitTestCase(TestCase):
    def test_key_gone_between_add_and_incr_counts_as_one(self):
        from unittest import mock
        from moses.services.otp_login import count_hit
        cache.clear()
        with mock.patch.object(cache, 'add'):  # add() "succeeds" but the key isn't there
            self.assertEqual(count_hit('moses:test', 60), 1)
        self.assertEqual(cache.get('moses:test'), 1)
        self.assertEqual(count_hit('moses:test', 60), 2)


def expire_pause(phone):
    User.objects.filter(phone_number=phone).update(phone_number_confirmation_code_sms_unlocks_at=None)


@override_settings(MOSES={**MOSES, "PHONE_OTP_REQUEST_IP_LIMIT": None,
                          "PHONE_OTP_CODES_PER_PHONE_LIMIT": (3, 86400)})
class OtpPerPhoneLimitTestCase(TestCase):
    def setUp(self):
        Site.objects.create(domain='a.com')
        Site.objects.create(domain='b.com')
        utils.SENT_SMS = {}
        utils.SENT_SMS_RAW = {}
        cache.clear()

    def send(self, phone=P1, domain='a.com'):
        expire_pause(phone)
        return test_client.otp_request(phone, domain)

    def test_fourth_code_is_refused(self):
        for _ in range(3):
            self.assertEqual(self.send().status_code, 200)
        utils.SENT_SMS = {}
        response = self.send()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(code(response), error_codes.PHONE_OTP_CODES_LIMIT_REACHED)
        self.assertEqual(utils.SENT_SMS, {})
        # other phone, and same phone on another site, are counted separately
        self.assertEqual(self.send(P2).status_code, 200)
        self.assertEqual(self.send(P1, 'b.com').status_code, 200)

    def test_used_codes_do_not_count(self):
        for _ in range(3):
            self.assertEqual(self.send().status_code, 200)
            response = test_client.otp_verify(P1, str(utils.SENT_SMS[P1]), 'a.com')
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.send().status_code, 200)

    def test_count_never_goes_below_zero(self):
        user = User(phone_number=P1, site=Site.objects.get(domain='a.com'))
        user.set_unusable_password()
        user.phone_number_confirmation_pin = 123456
        user.save()  # a code that was never counted (e.g. sent at registration)
        self.assertEqual(test_client.otp_verify(P1, '123456', 'a.com').status_code, 200)
        for _ in range(3):
            self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 429)

    def test_request_refused_by_pause_does_not_count(self):
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(test_client.otp_request(P1, 'a.com').status_code, 400)  # inside the pause
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 429)


@override_settings(MOSES={**MOSES, "PHONE_OTP_REQUEST_IP_LIMIT": None})
class OtpPerPhoneDefaultTestCase(TestCase):
    def test_default_has_no_per_phone_cap(self):
        Site.objects.create(domain='a.com')
        cache.clear()
        for _ in range(5):
            expire_pause(P1)
            self.assertEqual(test_client.otp_request(P1, 'a.com').status_code, 200)


class OtpFlagOffTestCase(TestCase):
    def test_flag_off_is_404(self):
        Site.objects.create(domain='a.com')
        self.assertEqual(test_client.otp_request(P1, 'a.com').status_code, 404)


# Without the IP limit: these tests make more failed verifies than it allows.
@override_settings(MOSES={**MOSES, "PHONE_OTP_REQUEST_IP_LIMIT": None})
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
        self.assertEqual(set(response.data), {'access', 'refresh', 'created'})
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

    def test_debug_master_code_is_not_accepted(self):
        user = User(phone_number=P1, site=self.site)
        user.set_unusable_password()
        user.save()  # pin 0
        with override_settings(DEBUG=True):
            self.assertEqual(test_client.otp_verify(P1, '123456', 'a.com').status_code, 400)
            pin = self.request_code()
            if pin != 123456:
                self.assertEqual(test_client.otp_verify(P1, '123456', 'a.com').status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.is_phone_number_confirmed)

    def otp_error(self, response):
        self.assertEqual(response.status_code, 400)
        return response.data['errors']['otp'][0]['error_code']

    def test_superuser_without_mfa_key_is_refused(self):
        pin = self.request_code()
        User.objects.filter(phone_number=P1).update(is_superuser=True)
        self.assertEqual(self.otp_error(test_client.otp_verify(P1, str(pin), 'a.com')),
                         error_codes.INVALID_OTP)
        with override_settings(DEBUG=True):
            self.assertEqual(self.otp_error(test_client.otp_verify(P1, str(pin), 'a.com', otp='000000')),
                             error_codes.INVALID_OTP)
        user = User.objects.get(phone_number=P1)
        self.assertFalse(user.is_phone_number_confirmed)
        self.assertEqual(user.phone_number_confirmation_pin, pin)

    def test_mfa_user_needs_totp(self):
        import pyotp
        key = pyotp.random_base32()
        pin = self.request_code()
        User.objects.filter(phone_number=P1).update(mfa_secret_key=key, is_phone_number_confirmed=True)
        self.assertEqual(self.otp_error(test_client.otp_verify(P1, str(pin), 'a.com')),
                         error_codes.INVALID_OTP)
        # pin not consumed: the same SMS code works with a valid TOTP
        response = test_client.otp_verify(P1, str(pin), 'a.com', otp=pyotp.TOTP(key).now())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {'access', 'refresh', 'created'})
        self.assertIs(response.data['created'], False)
        self.assertEqual(User.objects.get(phone_number=P1).mfa_secret_key, key)

    def squat(self, **fields):
        """An unconfirmed user who attached credentials nobody proved."""
        import pyotp
        pin = self.request_code()
        user = User.objects.get(phone_number=P1)
        user.set_password('squatter123')
        user.google_sub = 'g-sub'
        user.telegram_id = 'tg-id'
        user.mfa_secret_key = pyotp.random_base32()
        for name, value in fields.items():
            setattr(user, name, value)
        user.save()
        return pin

    def test_first_code_login_drops_unproven_credentials(self):
        pin = self.squat()
        response = test_client.otp_verify(P1, str(pin), 'a.com')
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data['created'], True)
        user = User.objects.get(phone_number=P1)
        self.assertTrue(user.is_phone_number_confirmed)
        self.assertFalse(user.has_usable_password())
        self.assertEqual((user.google_sub, user.telegram_id, user.mfa_secret_key), ('', '', ''))

    def test_unconfirmed_superuser_and_staff_keep_strict_totp_and_credentials(self):
        import pyotp
        for flags in ({'is_superuser': True, 'is_staff': True}, {'is_staff': True}):
            User.objects.all().delete()
            cache.clear()
            pin = self.squat(**flags)
            self.assertEqual(self.otp_error(test_client.otp_verify(P1, str(pin), 'a.com')),
                             error_codes.INVALID_OTP)
            user = User.objects.get(phone_number=P1)
            self.assertFalse(user.is_phone_number_confirmed)
            response = test_client.otp_verify(
                P1, str(pin), 'a.com', otp=pyotp.TOTP(user.mfa_secret_key).now())
            self.assertEqual(response.status_code, 200)
            user = User.objects.get(phone_number=P1)
            self.assertTrue(user.check_password('squatter123'))
            self.assertEqual((user.google_sub, user.telegram_id), ('g-sub', 'tg-id'))
            self.assertNotEqual(user.mfa_secret_key, '')

    def test_created_true_on_initial_confirmation_then_false(self):
        pin = self.request_code()
        response = test_client.otp_verify(P1, str(pin), 'a.com')
        self.assertIs(response.data['created'], True)
        utils.SENT_SMS = {}
        cache.clear()
        User.objects.filter(phone_number=P1).update(phone_number_confirmation_code_sms_unlocks_at=None)
        pin = self.request_code()
        response = test_client.otp_verify(P1, str(pin), 'a.com')
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data['created'], False)

    def test_created_false_for_user_confirmed_beforehand(self):
        user = User(phone_number=P1, site=self.site, is_phone_number_confirmed=True)
        user.set_unusable_password()
        user.save()
        pin = self.request_code()
        response = test_client.otp_verify(P1, str(pin), 'a.com')
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data['created'], False)

    def test_created_true_after_totp_failure(self):
        import pyotp
        key = pyotp.random_base32()
        pin = self.request_code()
        User.objects.filter(phone_number=P1).update(mfa_secret_key=key, is_superuser=True, is_staff=True)
        self.assertEqual(self.otp_error(test_client.otp_verify(P1, str(pin), 'a.com')),
                         error_codes.INVALID_OTP)
        self.assertFalse(User.objects.get(phone_number=P1).is_phone_number_confirmed)
        response = test_client.otp_verify(P1, str(pin), 'a.com', otp=pyotp.TOTP(key).now())
        self.assertIs(response.data['created'], True)

    def test_wrong_totp_counts_an_attempt(self):
        import pyotp
        key = pyotp.random_base32()
        pin = self.request_code()
        User.objects.filter(phone_number=P1).update(mfa_secret_key=key, is_phone_number_confirmed=True)
        wrong = '000000' if pyotp.TOTP(key).now() != '000000' else '111111'
        self.assertEqual(self.otp_error(test_client.otp_verify(P1, str(pin), 'a.com', otp=wrong)),
                         error_codes.INVALID_OTP)
        self.assertEqual(User.objects.get(phone_number=P1).phone_number_confirmation_attempts, 1)

    def test_ordinary_user_ignores_otp_field(self):
        pin = self.request_code()
        self.assertEqual(test_client.otp_verify(P1, str(pin), 'a.com', otp='garbage').status_code, 200)

    def test_non_string_inputs_are_400(self):
        import pyotp
        pin = self.request_code()
        bad = ({'a': 1}, ['x'], 1)
        for value in bad:
            for args in ((value, str(pin), 'a.com'), (P1, value, 'a.com'), (P1, str(pin), value)):
                response = test_client.otp_verify(*args)
                self.assertEqual(response.status_code, 400, args)
                self.assertIn('code', response.data['errors'])
        User.objects.filter(phone_number=P1).update(
            mfa_secret_key=pyotp.random_base32(), phone_number_confirmation_attempts=0,
            is_phone_number_confirmed=True)
        for value in bad:
            response = test_client.otp_verify(P1, str(pin), 'a.com', otp=value)
            self.assertEqual(self.otp_error(response), error_codes.INVALID_OTP)

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


class PasswordPathsTestCase(TestCase):
    def setUp(self):
        Site.objects.create(domain='a.com')

    def password_path_statuses(self):
        user = User.objects.get_or_create(phone_number=P2, site=Site.objects.get(domain='a.com'))[0]
        return [
            test_client.create_user(P1, 'pass12345', 'Ann', 'a@a.com', 'a.com')[1].status_code,
            test_client.login(P2, 'x', 'a.com')[1].status_code,
            test_client.update_password(user, 'x', 'y')[1].status_code,
            test_client.reset_password(P2, 'a.com').status_code,
            test_client.confirm_reset_password(P2, 'a.com', '1', 'y')[1].status_code,
        ]

    def test_password_paths_404_only_when_on(self):
        with override_settings(MOSES=MOSES):
            self.assertEqual(self.password_path_statuses(), [404] * 5)
        statuses = self.password_path_statuses()
        self.assertNotIn(404, statuses, statuses)

    def test_password_login_still_works_when_off(self):
        user = User(phone_number=P1, site=Site.objects.get(domain='a.com'), is_phone_number_confirmed=True)
        user.set_password('pass12345')
        user.save()
        self.assertEqual(test_client.login(P1, 'pass12345', 'a.com')[1].status_code, 200)


class MeEndpointTestCase(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient as DrfClient
        from django.urls import reverse
        self.reverse = reverse
        self.api = DrfClient()
        self.user = User(phone_number=P1, site=Site.objects.create(domain='a.com'), is_phone_number_confirmed=True)
        self.user.set_password('pass12345')
        self.user.save()
        self.api.force_authenticate(self.user)

    def test_get_and_patch_me_work_when_on(self):
        with override_settings(MOSES=MOSES):
            self.assertEqual(self.api.get(self.reverse('moses:customuser-me')).status_code, 200)
            self.assertEqual(
                self.api.patch(self.reverse('moses:customuser-me'), {'name': 'Bob'}, format='json').status_code, 200)


@override_settings(MOSES={**settings.MOSES, "PHONE_OTP_REQUEST_IP_LIMIT": (2, 600)})
class CodeSendingIpLimitTestCase(TestCase):
    """Every endpoint that sends a phone code shares otp_request's per-IP counter."""

    def setUp(self):
        from test_project.app_for_tests import drf_request_factory
        from rest_framework.test import force_authenticate
        from moses.views.user import UserViewSet
        self.factory, self.force_authenticate, self.views = drf_request_factory, force_authenticate, UserViewSet
        self.site = Site.objects.create(domain='a.com')
        self.user = User(phone_number=P1, site=self.site, is_phone_number_confirmed=True)
        self.user.set_password('pass12345')
        self.user.save()
        self.n = 0
        cache.clear()

    def call(self, action, ip, method='post'):
        self.n += 1
        phone = '+9965070001%02d' % self.n
        data = {
            'create': {'phone_number': phone, 'email': 'u%d@a.com' % self.n, 'password': 'pass12345',
                       'first_name': 'A', 'last_name': 'B', 'domain': 'a.com'},
            'reset_password': {'credential': P1, 'domain': 'a.com'},
            'me': {'phone_number': phone},
        }.get(action, {})
        User.objects.filter(pk=self.user.pk).update(
            password_reset_code_sms_unlocks_at=None, phone_number_confirmation_code_sms_unlocks_at=None)
        request = getattr(self.factory, method)('/', data, format='json', REMOTE_ADDR=ip)
        if action in ('request_phone_number_confirmation_pin', 'me'):
            self.force_authenticate(request, User.objects.get(pk=self.user.pk))
        return self.views.as_view({method: action})(request)

    def assert_limited(self, action, method='post'):
        cache.clear()
        for _ in range(2):
            self.assertLess(self.call(action, '1.1.1.1', method).status_code, 300, action)
        response = self.call(action, '1.1.1.1', method)
        self.assertEqual(response.status_code, 429, action)
        self.assertEqual(code(response), error_codes.TOO_FREQUENT_SMS_REQUESTS)
        self.assertNotEqual(self.call(action, '2.2.2.2', method).status_code, 429, action)

    def test_each_code_sending_endpoint_is_limited(self):
        self.assert_limited('create')
        self.assert_limited('reset_password')
        self.assert_limited('request_phone_number_confirmation_pin')
        self.assert_limited('me', 'patch')

    def test_shares_the_otp_request_counter(self):
        with override_settings(MOSES={**settings.MOSES, "PHONE_OTP_REQUEST_IP_LIMIT": (2, 600),
                                      "LOGIN_METHODS": ["WITH_PASSWORD", "WITHOUT_PASSWORD"]}):
            self.assertEqual(test_client.otp_request(P2, 'a.com', ip='1.1.1.1').status_code, 200)
            self.assertEqual(self.call('reset_password', '1.1.1.1').status_code, 204)
            self.assertEqual(self.call('reset_password', '1.1.1.1').status_code, 429)

    def test_profile_update_without_a_new_phone_is_not_counted(self):
        for _ in range(3):
            request = self.factory.patch('/', {'first_name': 'Bob'}, format='json', REMOTE_ADDR='1.1.1.1')
            self.force_authenticate(request, User.objects.get(pk=self.user.pk))
            self.assertEqual(self.views.as_view({'patch': 'me'})(request).status_code, 200)

    def test_no_limit_by_default(self):
        # settings.MOSES here already carries the class override, so drop the key.
        with override_settings(MOSES={k: v for k, v in settings.MOSES.items()
                                      if k != "PHONE_OTP_REQUEST_IP_LIMIT"}):
            for _ in range(4):
                self.assertNotEqual(self.call('create', '1.1.1.1').status_code, 429)


@override_settings(MOSES={**MOSES, "PHONE_OTP_CODE_TTL_SECONDS": 900})
class OtpCodeTtlTestCase(TestCase):
    def setUp(self):
        Site.objects.create(domain='a.com')
        utils.SENT_SMS = {}
        cache.clear()

    def request_code(self):
        self.assertEqual(test_client.otp_request(P1, 'a.com').status_code, 200)
        return utils.SENT_SMS[P1]

    def age_code(self, seconds):
        from datetime import timedelta
        from django.utils import timezone
        User.objects.filter(phone_number=P1).update(
            phone_number_confirmation_pin_created_at=timezone.now() - timedelta(seconds=seconds))

    def test_fresh_code_works_and_send_time_is_stored(self):
        from moses.services.otp_login import login_code_expired
        pin = self.request_code()
        user = User.objects.get(phone_number=P1)
        self.assertIsNotNone(user.phone_number_confirmation_pin_created_at)
        self.assertFalse(login_code_expired(user))
        self.age_code(899)
        self.assertEqual(test_client.otp_verify(P1, str(pin), 'a.com').status_code, 200)

    def test_expired_code_looks_wrong_and_costs_no_attempt(self):
        from moses.services.otp_login import login_code_expired
        pin = self.request_code()
        self.age_code(901)
        self.assertTrue(login_code_expired(User.objects.get(phone_number=P1)))
        response = test_client.otp_verify(P1, str(pin), 'a.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['code'][0]['error_code'],
                         error_codes.INCORRECT_CONFIRMATION_PIN)
        user = User.objects.get(phone_number=P1)
        self.assertEqual(user.phone_number_confirmation_attempts, 0)
        self.assertFalse(user.is_phone_number_confirmed)
        # a new code works again
        expire_pause(P1)
        self.assertEqual(test_client.otp_verify(P1, str(self.request_code()), 'a.com').status_code, 200)

    def test_pin_without_send_time_counts_as_expired(self):
        from moses.services.otp_login import login_code_expired
        self.request_code()
        User.objects.filter(phone_number=P1).update(phone_number_confirmation_pin_created_at=None)
        self.assertTrue(login_code_expired(User.objects.get(phone_number=P1)))

    def test_no_ttl_by_default(self):
        from moses.services.otp_login import login_code_expired
        pin = self.request_code()
        self.age_code(10 ** 6)
        with override_settings(MOSES=MOSES):
            self.assertFalse(login_code_expired(User.objects.get(phone_number=P1)))
            self.assertEqual(test_client.otp_verify(P1, str(pin), 'a.com').status_code, 200)

    def test_registration_code_gets_send_time(self):
        user = User.objects.create_user(phone_number=P2, password='pass12345', site=Site.objects.get(domain='a.com'))
        self.assertIsNotNone(user.phone_number_confirmation_pin_created_at)


@override_settings(MOSES=MOSES)
class OtpVerifyIpLimitTestCase(TestCase):
    """Failed otp_verify calls are counted per IP with PHONE_OTP_REQUEST_IP_LIMIT's numbers."""

    def setUp(self):
        Site.objects.create(domain='a.com')
        utils.SENT_SMS = {}
        cache.clear()

    def test_ip_refused_after_limit_failures_without_touching_the_user(self):
        self.assertEqual(test_client.otp_request(P1, 'a.com', ip='9.9.9.9').status_code, 200)
        pin = utils.SENT_SMS[P1]
        wrong = str(pin + 1 if pin < 999999 else pin - 1)
        self.assertEqual(test_client.otp_verify(P2, wrong, 'a.com', ip='1.1.1.1').status_code, 400)  # unknown
        for _ in range(2):
            self.assertEqual(test_client.otp_verify(P1, wrong, 'a.com', ip='1.1.1.1').status_code, 400)
        response = test_client.otp_verify(P1, str(pin), 'a.com', ip='1.1.1.1')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(code(response), error_codes.TOO_FREQUENT_SMS_REQUESTS)
        user = User.objects.get(phone_number=P1)
        self.assertEqual(user.phone_number_confirmation_attempts, 2)
        self.assertFalse(user.is_phone_number_confirmed)
        self.assertEqual(test_client.otp_verify(P1, str(pin), 'a.com', ip='2.2.2.2').status_code, 200)

    def test_successes_are_not_counted(self):
        for phone in (P1, P2, P3, P4):
            cache.delete('moses:otp_ip:9.9.9.9')
            self.assertEqual(test_client.otp_request(phone, 'a.com', ip='9.9.9.9').status_code, 200)
            self.assertEqual(
                test_client.otp_verify(phone, str(utils.SENT_SMS[phone]), 'a.com', ip='1.1.1.1').status_code, 200)

    def test_no_limit_when_setting_is_none(self):
        with override_settings(MOSES={**MOSES, "PHONE_OTP_REQUEST_IP_LIMIT": None}):
            for _ in range(5):
                self.assertEqual(test_client.otp_verify(P1, '111111', 'a.com', ip='1.1.1.1').status_code, 400)
