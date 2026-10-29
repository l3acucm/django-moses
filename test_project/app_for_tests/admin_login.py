from unittest import mock

import pyotp
from django.contrib.auth.signals import user_login_failed
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.test import TestCase, override_settings

from moses.models import CustomUser
from test_project.app_for_tests import utils

PW, NOPW = "WITH_PASSWORD", "WITHOUT_PASSWORD"
SENT = 'Если номер принадлежит сотруднику, код отправлен'
P_STAFF, P_PLAYER, P_UNKNOWN, P_SUPER = ('+99650700001%d' % i for i in (1, 2, 3, 4))
URL = '/admin/login/'


def moses(*methods):
    return {**settings.MOSES, "LOGIN_METHODS": list(methods), "PHONE_OTP_REQUEST_IP_LIMIT": (20, 600)}


class AdminLoginBase(TestCase):
    def setUp(self):
        cache.clear()
        utils.SENT_SMS = {}
        utils.SENT_SMS_RAW = {}
        # LoginView resolves the current site from the request host.
        self.site = Site.objects.create(domain='testserver')
        self.staff = self.make(P_STAFF, is_staff=True)
        self.player = self.make(P_PLAYER)
        self.key = utils.get_random_mfa_key()
        self.superuser = self.make(P_SUPER, is_staff=True, is_superuser=True, mfa_secret_key=self.key)

    def make(self, phone, **kw):
        user = CustomUser(site=self.site, phone_number=phone, is_phone_number_confirmed=True, **kw)
        user.set_password('abcxyz123')
        user.save()
        return user

    def post(self, **data):
        return self.client.post(URL, {'domain': 'testserver', **data})

    def send_code(self, phone):
        return self.post(username=phone, send_code='1')

    def pin(self, user):
        user.refresh_from_db()
        return user.phone_number_confirmation_pin

    def logged_in_as(self):
        return self.client.session.get('_auth_user_id')


@override_settings(MOSES=moses(PW, NOPW))
class BothMethodsTestCase(AdminLoginBase):
    def test_page_has_password_code_and_send_button(self):
        html = self.client.get(URL).content.decode()
        self.assertIn('name="password"', html)
        self.assertIn('name="code"', html)
        self.assertIn('name="send_code"', html)
        self.assertIn('Отправить код', html)

    def test_send_code_to_staff_sends_sms(self):
        response = self.send_code(P_STAFF)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, SENT)
        self.assertNotContains(response, 'errornote')
        self.assertIsNone(self.logged_in_as())
        self.assertEqual(utils.SENT_SMS[P_STAFF], self.pin(self.staff))

    def test_send_code_to_non_staff_or_unknown_sends_nothing(self):
        count = CustomUser.objects.count()
        for phone in (P_PLAYER, P_UNKNOWN):
            response = self.send_code(phone)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, SENT)
            self.assertNotContains(response, 'errornote')
        self.assertEqual(utils.SENT_SMS, {})
        self.assertEqual(self.pin(self.player), 0)
        self.assertEqual(CustomUser.objects.count(), count)

    def test_send_code_to_inactive_staff_sends_nothing(self):
        self.staff.is_active = False
        self.staff.save()
        self.assertContains(self.send_code(P_STAFF), SENT)
        self.assertEqual(utils.SENT_SMS, {})

    def test_send_code_inside_resend_pause_is_neutral(self):
        self.send_code(P_STAFF)
        utils.SENT_SMS = {}
        response = self.send_code(P_STAFF)
        self.assertContains(response, SENT)
        self.assertNotContains(response, 'errornote')
        self.assertEqual(utils.SENT_SMS, {})

    @override_settings(MOSES={**moses(PW, NOPW), "PHONE_OTP_REQUEST_IP_LIMIT": (1, 600)})
    def test_send_code_over_ip_limit_is_neutral_and_sends_nothing(self):
        self.send_code(P_PLAYER)
        response = self.send_code(P_STAFF)
        self.assertContains(response, SENT)
        self.assertEqual(utils.SENT_SMS, {})

    def test_sms_handler_failure_is_neutral(self):
        with mock.patch('moses.conf.settings.SEND_SMS_HANDLER', side_effect=RuntimeError('gateway down')):
            response = self.send_code(P_STAFF)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, SENT)
        self.assertNotContains(response, 'errornote')

    def test_failed_code_login_sends_user_login_failed(self):
        self.send_code(P_STAFF)
        got = []
        handler = lambda sender, credentials, **kw: got.append(credentials)
        user_login_failed.connect(handler)
        self.addCleanup(user_login_failed.disconnect, handler)
        self.post(username=P_STAFF, code=str((self.pin(self.staff) % 999999) + 1))
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]['username'], P_STAFF)
        self.assertNotIn('code', got[0])

    def test_staff_logs_in_by_code(self):
        self.send_code(P_STAFF)
        response = self.post(username=P_STAFF, code=str(self.pin(self.staff)))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.logged_in_as(), str(self.staff.pk))
        self.assertEqual(self.pin(self.staff), 0)

    def test_wrong_code_is_invalid_login(self):
        self.send_code(P_STAFF)
        pin = self.pin(self.staff)
        response = self.post(username=P_STAFF, code=str((pin % 999999) + 1))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errornote')
        self.assertIsNone(self.logged_in_as())
        self.assertEqual(self.pin(self.staff), pin)

    def test_non_staff_cannot_log_in_by_code(self):
        user = self.player
        user.phone_number_confirmation_pin = 123456
        user.save()
        response = self.post(username=P_PLAYER, code='123456')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.logged_in_as())
        user.refresh_from_db()
        self.assertEqual((user.phone_number_confirmation_pin, user.phone_number_confirmation_attempts), (123456, 0))

    def test_attempts_limit_is_form_error_not_500(self):
        self.send_code(P_STAFF)
        pin = self.pin(self.staff)
        for _ in range(settings.MOSES['PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT']):
            self.post(username=P_STAFF, code=str((pin % 999999) + 1))
        response = self.post(username=P_STAFF, code=str(pin))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errornote')
        self.assertIsNone(self.logged_in_as())

    def test_superuser_code_without_otp_fails_then_works_with_otp(self):
        self.send_code(P_SUPER)
        pin = self.pin(self.superuser)
        response = self.post(username=P_SUPER, code=str(pin))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errornote')
        self.assertIsNone(self.logged_in_as())
        response = self.post(username=P_SUPER, code=str(pin), otp=pyotp.TOTP(self.key).now())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.logged_in_as(), str(self.superuser.pk))

    def test_superuser_wrong_otp_does_not_consume_code(self):
        self.send_code(P_SUPER)
        pin = self.pin(self.superuser)
        good = pyotp.TOTP(self.key).now()
        response = self.post(username=P_SUPER, code=str(pin), otp='000000' if good != '000000' else '111111')
        self.assertContains(response, 'errornote')
        self.assertIsNone(self.logged_in_as())
        self.assertEqual(self.pin(self.superuser), pin)
        self.post(username=P_SUPER, code=str(pin), otp=good)
        self.assertEqual(self.logged_in_as(), str(self.superuser.pk))

    def test_superuser_without_mfa_key_cannot_log_in_by_code(self):
        self.superuser.mfa_secret_key = ''
        self.superuser.save()
        self.send_code(P_SUPER)
        self.post(username=P_SUPER, code=str(self.pin(self.superuser)), otp='000000')
        self.assertIsNone(self.logged_in_as())

    def test_password_login_still_works(self):
        response = self.post(username=P_STAFF, password='abcxyz123')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.logged_in_as(), str(self.staff.pk))

    def test_code_preferred_over_password(self):
        self.send_code(P_STAFF)
        self.post(username=P_STAFF, password='wrong-password', code=str(self.pin(self.staff)))
        self.assertEqual(self.logged_in_as(), str(self.staff.pk))

    def test_neither_password_nor_code_is_error(self):
        response = self.post(username=P_STAFF)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errornote')
        self.assertIsNone(self.logged_in_as())


@override_settings(MOSES=moses(PW))
class PasswordOnlyTestCase(AdminLoginBase):
    def test_no_code_field_or_button(self):
        html = self.client.get(URL).content.decode()
        self.assertIn('name="password"', html)
        self.assertNotIn('name="code"', html)
        self.assertNotIn('name="send_code"', html)

    def test_code_and_send_code_are_ignored(self):
        self.send_code(P_STAFF)
        self.assertEqual(utils.SENT_SMS, {})
        self.staff.phone_number_confirmation_pin = 123456
        self.staff.save()
        self.post(username=P_STAFF, code='123456')
        self.assertIsNone(self.logged_in_as())

    def test_password_login(self):
        self.post(username=P_STAFF, password='abcxyz123')
        self.assertEqual(self.logged_in_as(), str(self.staff.pk))


@override_settings(MOSES=moses(NOPW))
class CodeOnlyTestCase(AdminLoginBase):
    def test_no_password_field(self):
        html = self.client.get(URL).content.decode()
        self.assertNotIn('name="password"', html)
        self.assertIn('name="code"', html)
        self.assertIn('name="send_code"', html)

    def test_password_is_ignored(self):
        self.post(username=P_STAFF, password='abcxyz123')
        self.assertIsNone(self.logged_in_as())

    def test_code_login(self):
        self.send_code(P_STAFF)
        response = self.post(username=P_STAFF, code=str(self.pin(self.staff)))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.logged_in_as(), str(self.staff.pk))
