from unittest import mock

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient as DrfClient, APIRequestFactory
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from django.contrib.auth.models import Group, Permission
from rest_framework_simplejwt.tokens import RefreshToken

from moses.authentication import JWTAuthentication
from moses.common.exceptions import CustomAPIException
from moses.models import CustomUser
from moses.services.anonymize import anonymize_user
from moses.signals import user_anonymized
from test_project.app_for_tests import APIClient
from test_project.app_for_tests import utils

PW, NOPW = "WITH_PASSWORD", "WITHOUT_PASSWORD"
P1, P2, P3 = ('+99650700002%d' % i for i in (1, 2, 3))
PASSWORD = 'pass12345'


def moses(*methods):
    return {**settings.MOSES, "LOGIN_METHODS": list(methods)}


def make(site, phone, password=PASSWORD, **kw):
    kw.setdefault('is_email_confirmed', True)
    user = CustomUser(
        site=site, phone_number=phone, first_name='Ann', last_name='Lee', email=f'{phone[1:]}@a.com',
        email_candidate='new@a.com', phone_number_candidate='+996700000999', is_phone_number_confirmed=True,
        google_sub='g' + phone, telegram_id='tg' + phone, mfa_secret_key=utils.get_random_mfa_key(),
        email_confirmation_pin=11, email_candidate_confirmation_pin=12, phone_number_confirmation_pin=13,
        phone_number_candidate_confirmation_pin=14, password_reset_code=15, **kw)
    if password:
        user.set_password(password)
    else:
        user.set_unusable_password()
    user.save()
    return user


class AnonymizedAssertions:
    def assert_anonymized(self, user, old_phone):
        user = CustomUser.objects.get(pk=user.pk)
        self.assertEqual((user.first_name, user.last_name), ('DELETED', 'DELETED'))
        self.assertNotEqual(user.phone_number, old_phone)
        self.assertTrue(user.phone_number)
        self.assertEqual((user.email, user.email_candidate, user.phone_number_candidate), ('', '', ''))
        self.assertFalse(user.has_usable_password())
        self.assertEqual((user.google_sub, user.telegram_id, user.mfa_secret_key), ('', '', ''))
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_phone_number_confirmed)
        self.assertFalse(user.is_email_confirmed)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.groups.exists())
        self.assertFalse(user.user_permissions.exists())
        self.assertEqual(
            (user.email_confirmation_pin, user.email_candidate_confirmation_pin,
             user.phone_number_confirmation_pin, user.phone_number_candidate_confirmation_pin),
            (0, 0, 0, 0))
        self.assertIsNone(user.password_reset_code)
        return user

    def assert_untouched(self, user):
        fresh = CustomUser.objects.get(pk=user.pk)
        self.assertEqual(
            (fresh.first_name, fresh.phone_number, fresh.email, fresh.is_active, fresh.password),
            (user.first_name, user.phone_number, user.email, user.is_active, user.password))


class SelfDeleteTestCase(AnonymizedAssertions, TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain='a.com')
        self.api = DrfClient()
        self.received = []
        user_anonymized.connect(self.on_anonymized)
        self.addCleanup(user_anonymized.disconnect, self.on_anonymized)

    def on_anonymized(self, sender, user, **kwargs):
        self.received.append((sender, user.pk))

    def delete_me(self, user, data=None):
        self.api.force_authenticate(user)
        return self.api.delete(reverse('moses:customuser-me'), data or {}, format='json')

    def test_no_login_methods_key_anonymizes_with_password(self):
        self.assertNotIn('LOGIN_METHODS', settings.MOSES)
        user = make(self.site, P1)
        response = self.delete_me(user, {'current_password': PASSWORD})
        self.assertEqual(response.status_code, 204)
        self.assert_anonymized(user, P1)
        self.assertEqual(self.received, [(CustomUser, user.pk)])

    @override_settings(MOSES=moses(PW, NOPW))
    def test_both_methods_anonymizes(self):
        user = make(self.site, P1)
        self.assertEqual(self.delete_me(user, {'current_password': PASSWORD}).status_code, 204)
        self.assert_anonymized(user, P1)

    def test_wrong_password_400_unchanged(self):
        user = make(self.site, P1)
        self.assertEqual(self.delete_me(user, {'current_password': 'nope'}).status_code, 400)
        self.assert_untouched(user)
        self.assertEqual(self.received, [])

    @override_settings(MOSES=moses(NOPW))
    def test_no_usable_password_needs_no_password(self):
        user = make(self.site, P1, password=None)
        self.assertEqual(self.delete_me(user).status_code, 204)
        self.assert_anonymized(user, P1)

    def test_superuser_403_unchanged(self):
        user = make(self.site, P1, is_staff=True, is_superuser=True)
        response = self.delete_me(user, {'current_password': PASSWORD})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['errors'][''][0]['error_code'], 'superuser_cannot_be_deleted')
        self.assert_untouched(user)
        self.assertEqual(self.received, [])

    def test_destroy_by_id_anonymizes(self):
        user = make(self.site, P1)
        self.api.force_authenticate(user)
        response = self.api.delete(
            reverse('moses:customuser-detail', args=[user.pk]), {'current_password': PASSWORD}, format='json')
        self.assertEqual(response.status_code, 204)
        self.assert_anonymized(user, P1)


class AnonymizeServiceTestCase(AnonymizedAssertions, TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain='a.com')

    def test_staff_groups_permissions_stripped(self):
        user = make(self.site, P1, is_staff=True)
        user.groups.add(Group.objects.create(name='g'))
        user.user_permissions.add(Permission.objects.first())
        anonymize_user(user)
        self.assert_anonymized(user, P1)

    def test_old_access_token_rejected(self):
        user = make(self.site, P1)
        token = str(RefreshToken.for_user(user).access_token)
        request = APIRequestFactory().get('/', HTTP_AUTHORIZATION='Bearer ' + token)
        self.assertEqual(JWTAuthentication().authenticate(request)[0].pk, user.pk)
        anonymize_user(user)
        with self.assertRaises(AuthenticationFailed):
            JWTAuthentication().authenticate(request)

    def test_raising_receiver_rolls_back(self):
        user = make(self.site, P1)
        before = CustomUser.objects.get(pk=user.pk)
        def boom(sender, user, **kwargs):
            raise RuntimeError('boom')
        user_anonymized.connect(boom)
        self.addCleanup(user_anonymized.disconnect, boom)
        with self.assertRaises(RuntimeError):
            anonymize_user(user)
        self.assert_untouched(before)

    def test_twice_no_error(self):
        user = make(self.site, P1)
        anonymize_user(user)
        first = CustomUser.objects.get(pk=user.pk).phone_number
        anonymize_user(user)
        self.assertNotEqual(self.assert_anonymized(user, P1).phone_number, first)

    def test_placeholder_collision_retried(self):
        taken = make(self.site, P2)
        user = make(self.site, P1)
        with mock.patch('moses.services.anonymize.secrets.token_hex', side_effect=['aaaaaa', 'aaaaaa', 'bbbbbb']):
            anonymize_user(taken)
            anonymize_user(user)
        self.assertEqual(CustomUser.objects.get(pk=user.pk).phone_number, 'deleted-bbbbbb')

    def test_superuser_refused(self):
        user = make(self.site, P1, is_staff=True, is_superuser=True)
        with self.assertRaises(CustomAPIException) as ctx:
            anonymize_user(user)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.errors_repr[''][0]['error_code'], 'superuser_cannot_be_deleted')
        self.assert_untouched(user)

    @override_settings(MOSES={**moses(NOPW), "PHONE_OTP_REQUEST_IP_LIMIT": None})
    def test_old_phone_registers_a_new_user(self):
        cache.clear()
        user = make(self.site, P1)
        anonymize_user(user)
        self.assertEqual(APIClient('').otp_request(P1, 'a.com').status_code, 200)
        new = CustomUser.objects.get(site=self.site, phone_number=P1)
        self.assertNotEqual(new.pk, user.pk)
        self.assertTrue(CustomUser.objects.filter(pk=user.pk).exists())


class AdminDeleteTestCase(AnonymizedAssertions, TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain='a.com')
        self.admin = make(self.site, P3, is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)

    def bulk_delete(self, *users):
        return self.client.post(reverse('admin:moses_customuser_changelist'), {
            'action': 'delete_selected', '_selected_action': [str(u.pk) for u in users], 'post': 'yes'})

    def test_single_delete_anonymizes(self):
        user = make(self.site, P1)
        response = self.client.post(reverse('admin:moses_customuser_delete', args=[user.pk]), {'post': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assert_anonymized(user, P1)

    def test_single_delete_of_superuser_refused(self):
        response = self.client.get(reverse('admin:moses_customuser_delete', args=[self.admin.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('admin:moses_customuser_delete', args=[self.admin.pk]), {'post': 'yes'})
        self.assertEqual(response.status_code, 403)
        self.assert_untouched(self.admin)
        self.assertFalse(LogEntry.objects.exists())

    def test_bulk_delete_anonymizes(self):
        a, b = make(self.site, P1), make(self.site, P2)
        self.assertEqual(self.bulk_delete(a, b).status_code, 302)
        self.assert_anonymized(a, P1)
        self.assert_anonymized(b, P2)
        self.assertEqual(CustomUser.objects.count(), 3)

    def test_bulk_with_superuser_refuses_everything(self):
        user = make(self.site, P1)
        # The action's first step shows «Cannot delete» instead of a confirmation…
        response = self.client.post(reverse('admin:moses_customuser_changelist'), {
            'action': 'delete_selected', '_selected_action': [str(user.pk), str(self.admin.pk)]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['perms_lacking'])
        # …and a forged confirmation is refused outright.
        self.assertEqual(self.bulk_delete(user, self.admin).status_code, 403)
        self.assert_untouched(user)
        self.assert_untouched(self.admin)
        self.assertFalse(LogEntry.objects.exists())

    def test_confirmation_page_lists_only_users(self):
        user = make(self.site, P1)
        response = self.client.get(reverse('admin:moses_customuser_delete', args=[user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['deleted_objects'], [str(user)])
