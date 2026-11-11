from django.conf import settings
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from moses.conf import Settings, default_settings, login_methods
from moses.models import CustomUser
from test_project.app_for_tests import APIClient

test_client = APIClient('')
PW, NOPW = "WITH_PASSWORD", "WITHOUT_PASSWORD"


def moses(methods=None):
    d = {k: v for k, v in settings.MOSES.items() if k != "LOGIN_METHODS"}
    if methods is not None:
        d["LOGIN_METHODS"] = methods
    return d


class LoginMethodsTestCase(TestCase):
    def setUp(self):
        cache.clear()
        site = Site.objects.create(domain='lm.com')
        self.user = CustomUser(site=site, phone_number='+996507000001', email='a@lm.com',
                               is_phone_number_confirmed=True)
        self.user.set_password('abcxyz123')
        self.user.save()

    def probe(self):
        """status codes of every gated endpoint"""
        return {
            'login': test_client.login('+996507000001', 'abcxyz123', 'lm.com')[1].status_code,
            'create': test_client.create_user('+996507000002', 'abcxyz123', 'n', 'n@lm.com', 'lm.com')[1].status_code,
            'set_password': test_client.update_password(self.user, 'abcxyz123', 'abcxyz456xx')[1].status_code,
            'reset': test_client.reset_password('+996507000001', 'lm.com').status_code,
            'reset_confirm': test_client.confirm_reset_password('+996507000001', 'lm.com', 1, 'abcxyz456xx')[1].status_code,
            'otp_request': test_client.otp_request('+996507000003', 'lm.com').status_code,
            'otp_verify': test_client.otp_verify('+996507000001', 1, 'lm.com').status_code,
        }

    def test_default_is_password_only(self):
        with override_settings(MOSES=moses()):
            p = self.probe()
        self.assertEqual(p['login'], 200)
        self.assertEqual(p['otp_request'], 404)
        self.assertEqual(p['otp_verify'], 404)
        for k in ('create', 'set_password', 'reset', 'reset_confirm'):
            self.assertNotEqual(p[k], 404, k)

    def test_without_password_only(self):
        with override_settings(MOSES=moses([NOPW])):
            p = self.probe()
        for k in ('login', 'create', 'set_password', 'reset', 'reset_confirm'):
            self.assertEqual(p[k], 404, k)
        self.assertNotEqual(p['otp_request'], 404)
        self.assertNotEqual(p['otp_verify'], 404)

    def test_both(self):
        with override_settings(MOSES=moses([PW, NOPW])):
            p = self.probe()
        self.assertEqual(p['login'], 200)
        self.assertEqual(p['otp_request'], 200)
        for k, v in p.items():
            self.assertNotEqual(v, 404, k)

    def test_validation(self):
        with override_settings(MOSES={}):  # Settings prefers django settings over the explicit dict
            self.assertEqual(login_methods(), frozenset({PW}))
            self.assertEqual(Settings(default_settings, {"LOGIN_METHODS": [PW, NOPW]}).LOGIN_METHODS, [PW, NOPW])
            for bad in ([], ["FOO"], [PW, "FOO"]):
                with self.assertRaises(ImproperlyConfigured):
                    Settings(default_settings, {"LOGIN_METHODS": bad})

    def test_removed_key_and_non_iterable_rejected(self):
        with override_settings(MOSES={}):
            with self.assertRaisesMessage(ImproperlyConfigured, "PHONE_OTP_LOGIN was removed"):
                Settings(default_settings, {"PHONE_OTP_LOGIN": False})
            for bad in (None, 5, "WITH_PASSWORD"):
                with self.assertRaises(ImproperlyConfigured):
                    Settings(default_settings, {"LOGIN_METHODS": bad})
