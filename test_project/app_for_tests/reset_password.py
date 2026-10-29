from django.conf import settings as django_settings
from django.test import TestCase, override_settings
from django.utils.timezone import now

from moses.common import error_codes
from moses.conf import settings as moses_settings
from moses.models import CustomUser
from test_project.app_for_tests import APIClient, utils

test_client = APIClient('')


class ResetPasswordTestCase(TestCase):
    fixtures = ['reset_password']

    def setUp(self):
        self.user1 = CustomUser.objects.get(id=1)
        self.user2 = CustomUser.objects.get(id=2)
        utils.SENT_SMS = {}

    def test_cannot_reset_password_on_non_existent_site(self):
        response = test_client.reset_password(
            '+0',
            'not.exists.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['errors']['credential'][0]['error_code'],
            error_codes.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN
        )
        self.assertNotIn('+0', utils.SENT_SMS)

    def test_cannot_reset_password_on_site_that_not_registered_on(self):
        response = test_client.reset_password(
            '+1',
            'exists.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['credential'][0]['error_code'],
                         error_codes.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN)
        self.assertNotIn('+0', utils.SENT_SMS)

    def test_can_reset_password_on_site_that_registered_on(self):
        response = test_client.get_sms_unlock_time('password_reset', '+0', 'exists.com')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['unlocks_at'])
        response = test_client.reset_password(
            '+0',
            'exists.com'
        )
        self.assertEqual(response.status_code, 204)
        self.assertIn('+0', utils.SENT_SMS)
        self.assertFalse(self.user1.check_password('123123123'))
        response = test_client.get_sms_unlock_time('password_reset', '+0', 'exists.com')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.data['unlocks_at'], now())
        self.user1, response = test_client.confirm_reset_password('+0', 'exists2.com', utils.SENT_SMS['+0'], '123123123')
        if self.user1 is None:
            self.user1 = CustomUser.objects.get(id=1)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.user1.check_password('123123123'))
        self.user1, response = test_client.confirm_reset_password('+0', 'exists2.com', 100,
                                                                  '123123123')
        if self.user1 is None:
            self.user1 = CustomUser.objects.get(id=1)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.user1.check_password('123123123'))
        self.user1, response = test_client.confirm_reset_password('+0', 'exists.com', utils.SENT_SMS['+0'] + 1, '123123123')
        if self.user1 is None:
            self.user1 = CustomUser.objects.get(id=1)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.user1.check_password('123123123'))
        self.user1, response = test_client.confirm_reset_password('+0', 'exists.com', utils.SENT_SMS['+0'], '123123123')
        self.assertEqual(response.status_code, 204)
        self.assertTrue(self.user1.check_password('123123123'))

    def test_cannot_reset_password_on_site_that_is_not_registered_on(self):
        response = test_client.reset_password(
            '+0',
            'exists2.com'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['credential'][0]['error_code'],
                         error_codes.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN)


class ResetPasswordPhoneConfirmationGateTestCase(TestCase):
    """MOSES['CAN_RESET_PASSWORD_WITHOUT_PHONE_NUMBER_CONFIRMATION'] (default
    False) keeps ResetPasswordSerializer matching only a confirmed phone/email
    — same as before this setting existed. On, an unconfirmed user can still
    request a reset."""
    fixtures = ['reset_password']

    def setUp(self):
        self.user1 = CustomUser.objects.get(id=1)
        self.user1.is_phone_number_confirmed = False
        self.user1.save()
        utils.SENT_SMS = {}

    def test_blocks_reset_by_default_when_phone_not_confirmed(self):
        response = test_client.reset_password('+0', 'exists.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['errors']['credential'][0]['error_code'],
            error_codes.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN)
        self.assertNotIn('+0', utils.SENT_SMS)

    # override_settings(MOSES=...) replaces the whole MOSES dict rather than
    # merging into it, so it must carry the project's own settings (e.g.
    # SEND_SMS_HANDLER) forward explicitly, not just the one flag under test.
    @override_settings(MOSES={
        **django_settings.MOSES,
        'CAN_RESET_PASSWORD_WITHOUT_PHONE_NUMBER_CONFIRMATION': True,
    })
    def test_allows_reset_when_setting_enabled(self):
        response = test_client.reset_password('+0', 'exists.com')
        self.assertEqual(response.status_code, 204)
        self.assertIn('+0', utils.SENT_SMS)


class ResetPasswordCodeAttemptsTestCase(TestCase):
    """A reset code allows PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT wrong guesses, then
    it is burned; the right code works once; a new reset code restores the attempts."""
    fixtures = ['reset_password']

    def setUp(self):
        utils.SENT_SMS = {}
        self.limit = moses_settings.PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT
        self.assertEqual(test_client.reset_password('+0', 'exists.com').status_code, 204)
        self.code = utils.SENT_SMS['+0']

    def confirm(self, code, password='123123123'):
        return test_client.confirm_reset_password('+0', 'exists.com', code, password)

    def test_wrong_codes_burn_the_code(self):
        for _ in range(self.limit):
            user, response = self.confirm(self.code + 1)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data['errors']['code'][0]['error_code'],
                             error_codes.INVALID_CONFIRMATION_CODE)
        self.assertIsNone(user.password_reset_code)
        user, response = self.confirm(self.code)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors'][''][0]['error_code'], error_codes.ATTEMPTS_LIMIT_REACHED)
        self.assertFalse(user.check_password('123123123'))

    def test_right_code_works_once(self):
        user, response = self.confirm(self.code + 1)
        self.assertEqual(user.password_reset_code_attempts, 1)
        user, response = self.confirm(self.code)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(user.check_password('123123123'))
        self.assertIsNone(user.password_reset_code)
        self.assertEqual(user.password_reset_code_attempts, 0)
        user, response = self.confirm(self.code, 'other-pass-456')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors']['code'][0]['error_code'],
                         error_codes.INVALID_CONFIRMATION_CODE)
        self.assertTrue(user.check_password('123123123'))

    def test_new_reset_code_restores_attempts(self):
        for _ in range(self.limit):
            self.confirm(self.code + 1)
        CustomUser.objects.filter(id=1).update(password_reset_code_sms_unlocks_at=None)
        self.assertEqual(test_client.reset_password('+0', 'exists.com').status_code, 204)
        self.assertEqual(CustomUser.objects.get(id=1).password_reset_code_attempts, 0)
        user, response = self.confirm(utils.SENT_SMS['+0'])
        self.assertEqual(response.status_code, 204)
        self.assertTrue(user.check_password('123123123'))

    def test_new_email_reset_code_restores_attempts(self):
        CustomUser.objects.filter(id=1).update(
            is_email_confirmed=True, password_reset_code_attempts=self.limit, password_reset_code_sms_unlocks_at=None)
        self.assertEqual(test_client.reset_password('foo@foo.com', 'exists.com').status_code, 204)
        self.assertEqual(CustomUser.objects.get(id=1).password_reset_code_attempts, 0)


@override_settings(MOSES={**django_settings.MOSES, 'PHONE_OTP_CODES_PER_PHONE_LIMIT': (3, 86400)})
class ResetPasswordPerPhoneCapTestCase(TestCase):
    """Phone reset codes share PHONE_OTP_CODES_PER_PHONE_LIMIT's count of unused codes with login codes."""
    fixtures = ['reset_password']

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        utils.SENT_SMS = {}

    def reset(self, credential='+0'):
        CustomUser.objects.filter(id=1).update(password_reset_code_sms_unlocks_at=None)
        return test_client.reset_password(credential, 'exists.com')

    def assert_capped(self):
        utils.SENT_SMS = {}
        response = self.reset()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['errors'][''][0]['error_code'], error_codes.PHONE_OTP_CODES_LIMIT_REACHED)
        self.assertEqual(utils.SENT_SMS, {})

    def test_fourth_reset_code_is_refused(self):
        for _ in range(3):
            self.assertEqual(self.reset().status_code, 204)
        self.assert_capped()

    def test_shared_with_login_codes(self):
        from moses.services.otp_login import send_login_code
        self.assertEqual(self.reset().status_code, 204)
        for _ in range(2):
            CustomUser.objects.filter(id=1).update(phone_number_confirmation_code_sms_unlocks_at=None)
            send_login_code(CustomUser.objects.get(id=1))
        self.assert_capped()

    def test_used_reset_code_does_not_count(self):
        for _ in range(3):
            self.assertEqual(self.reset().status_code, 204)
            _, response = test_client.confirm_reset_password('+0', 'exists.com', utils.SENT_SMS['+0'], '123123123')
            self.assertEqual(response.status_code, 204)
        self.assertEqual(self.reset().status_code, 204)

    def test_email_reset_waits_like_phone_and_is_not_counted(self):
        CustomUser.objects.filter(id=1).update(is_email_confirmed=True)
        self.assertEqual(test_client.reset_password('foo@foo.com', 'exists.com').status_code, 204)
        response = test_client.reset_password('foo@foo.com', 'exists.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['errors'][''][0]['error_code'], error_codes.TOO_FREQUENT_SMS_REQUESTS)
        for _ in range(3):
            self.assertEqual(self.reset().status_code, 204)

    def test_no_cap_by_default(self):
        with override_settings(MOSES={k: v for k, v in django_settings.MOSES.items()
                                      if k != 'PHONE_OTP_CODES_PER_PHONE_LIMIT'}):
            for _ in range(5):
                self.assertEqual(self.reset().status_code, 204)
