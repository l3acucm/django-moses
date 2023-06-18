import base64
import random
import string
from datetime import datetime

import pyotp
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import translation, timezone
from django.utils.timezone import now
from django.utils.translation import gettext as _
from djoser.compat import get_user_email_field_name, get_user_email
from djoser.conf import settings as djoser_settings
from djoser.utils import ActionViewMixin, logout_user, encode_uid
from rest_framework import generics, status
from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenViewBase

from moses.conf import settings as moses_settings
from moses.decorators import otp_required
from moses.models import CustomUser
from moses.serializers import PasswordResetSerializer, ShortCustomUserSerializer, \
    TokenObtainPairSerializer, PublicCustomUserSerializer, PinSerializer, MFASerializer

LANGUAGES_LIST = [l[0] for l in moses_settings.LANGUAGE_CHOICES]


class ConfirmPhoneNumber(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PinSerializer

    def post(self, request):
        candidate_phone_number = request.user.phone_number_candidate
        confirmation_result = request.user.try_to_confirm_phone_number(
            request.data['pin'],
            request.data.get('candidate_pin', '')
        )
        if candidate_phone_number:
            if confirmation_result:
                with translation.override(request.user.preferred_language):
                    send_mail(_("Phone number changed"),
                              _(
                                  f"Your phone number has been changed. If it happened without your desire - contact us by email support@{moses_settings.DOMAIN}."),
                              'noreply@' + moses_settings.DOMAIN, [request.user.email])
                return Response({'result': 'ok'})
        return Response({'non_field_errors': ['invalid_pin']}, status.HTTP_400_BAD_REQUEST)


class ConfirmEmail(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PinSerializer

    def post(self, request):
        candidate_email = request.user.email_candidate
        confirmation_result = request.user.try_to_confirm_email(request.data['pin'],
                                                                request.data.get('candidate_pin', ''))
        if confirmation_result:
            if candidate_email:
                with translation.override(request.user.preferred_language):
                    send_mail(_("Email changed"),
                              _(
                                  f"Your email has been changed. If it happened without your desire - contact us by email support@{moses_settings.DOMAIN}."),
                              'noreply@' + moses_settings.DOMAIN, [candidate_email])
            return Response({'result': 'ok'})
        return Response({'non_field_errors': ['invalid_pin']}, status.HTTP_400_BAD_REQUEST)


class TokenObtainPairView(TokenViewBase):
    serializer_class = TokenObtainPairSerializer

    def get_serializer_context(self):
        return {'request': self.request}


class ValidateAuthView(generics.GenericAPIView):
    def post(self, request):
        if request.user.is_authenticated:
            if request.user.verify_mfa_otp(request.data.get('mfa_code')):
                return Response({'user_id': request.user.id, 'verified_at': int(datetime.timestamp(now()))})
            else:
                return Response({'non_field_errors': ['invalid_otp']}, status.HTTP_400_BAD_REQUEST)
        return Response({'non_field_errors': ['not_authenticated']}, status.HTTP_400_BAD_REQUEST)


class CheckEmailAvailability(generics.GenericAPIView):
    serializer_class = PublicCustomUserSerializer

    def get(self, request):
        return Response({'result': not CustomUser.objects.filter(email=request.GET.get('email')).exists()},
                        status=status.HTTP_200_OK)


class CheckIsMFAEnabled(generics.GenericAPIView):
    serializer_class = PublicCustomUserSerializer
    permission_classes = list()

    def get(self, request):
        u_qs = CustomUser.objects.filter(phone_number=self.request.GET.get('phone_number'))
        result = u_qs.exists() and bool(u_qs.first().mfa_secret_key)
        return Response({'result': result}, status=status.HTTP_200_OK)


class MFAView(generics.GenericAPIView):
    serializer_class = MFASerializer

    @otp_required
    def post(self, request):
        if request.data['action'] == 'get_key':
            mfa_secret_key = base64.b32encode(
                bytes(''.join(random.choice(string.ascii_letters) for _ in range(100)).encode('utf-8'))).decode('utf-8')
            return Response({'mfa_url': pyotp.totp.TOTP(mfa_secret_key.encode('utf-8'))
                            .provisioning_uri(f"{request.user.first_name} {request.user.last_name}", moses_settings.DOMAIN),
                             'mfa_secret_key': mfa_secret_key})

        elif not request.user.mfa_secret_key and request.data['action'] == 'enable':
            mfa_secret_key = request.data.get('mfa_secret_key')
            otp = request.headers.get('otp', '')
            if pyotp.totp.TOTP(mfa_secret_key.encode('utf-8')).verify(otp):
                request.user.mfa_secret_key = mfa_secret_key
                request.user.save()
                return Response({'success': 'mfa has been successfully disabled'})
            return Response({'non_field_errors': ['invalid_otp']}, status=status.HTTP_400_BAD_REQUEST)

        elif request.user.mfa_secret_key and request.data['action'] == 'disable':
            request.user.mfa_secret_key = ''
            request.user.save()
            return Response({'success': 'mfa has been successfully disabled'})


class ResetPassword(ActionViewMixin, generics.GenericAPIView):
    serializer_class = PasswordResetSerializer
    _users = None

    permission_classes = list()

    def _action(self, serializer):
        if 'email' in serializer.data:
            for user in self.get_users_by_email(serializer.data['email']):
                if user.is_email_confirmed:
                    try:
                        self.send_password_reset_email(user)
                    except ValueError as e:
                        return Response({'error': str(e)},
                                        status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({'non_field_errors': ['email_not_activated']},
                                    status=status.HTTP_400_BAD_REQUEST)

        if 'phone_number' in serializer.data:
            users = self.get_users_by_phone_number(serializer.data['phone_number'])
            if not users:
                return Response({'non_field_errors': ['phone_number_not_found']},
                                status=status.HTTP_400_BAD_REQUEST)
            for user in users:
                if user.is_phone_number_confirmed:
                    if not user.last_password_reset_sms_sent_at or (
                            timezone.now() - user.last_password_reset_sms_sent_at).days > 0:
                        try:
                            self.send_password_reset_sms(user)
                        except ValueError as e:
                            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({'non_field_errors': ['too_frequent_sms_request']},
                                        status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({'non_field_errors': ['phone_number_not_confirmed']},
                                    status=status.HTTP_400_BAD_REQUEST)
        return Response({}, status=status.HTTP_204_NO_CONTENT)

    def get_users_by_email(self, email):
        if self._users is None:
            email_field_name = get_user_email_field_name(CustomUser)
            users = CustomUser._default_manager.filter(**{
                email_field_name + '__iexact': email
            })
            self._users = users
        return self._users

    def get_users_by_phone_number(self, phone_number):
        if self._users is None:
            users = CustomUser._default_manager.filter(**{
                'phone_number__iexact': phone_number
            })
            self._users = users
        return self._users

    def send_password_reset_email(self, user):
        context = {'user': user}
        to = [get_user_email(user)]
        if user.is_email_confirmed:
            with translation.override(user.preferred_language):
                djoser_settings.EMAIL.password_reset(self.request, context).send(to)
        else:
            raise ValueError(_("Email is not confirmed"))

    def send_password_reset_sms(self, user):
        url = settings.URL_PREFIX + '/' + djoser_settings.PASSWORD_RESET_CONFIRM_URL.format(
            token=default_token_generator.make_token(user),
            uid=encode_uid(user.pk))
        moses_settings.SEND_SMS_HANDLER(to=user.phone_number, body=url)
        user.last_password_reset_sms_sent_at = timezone.now()
        user.save()


class SetPasswordView(ActionViewMixin, generics.GenericAPIView):
    """
    Use this endpoint to change user password.
    """
    permission_classes = djoser_settings.PERMISSIONS.set_password

    def get_serializer_class(self):
        if djoser_settings.SET_PASSWORD_RETYPE:
            return djoser_settings.SERIALIZERS.set_password_retype
        return djoser_settings.SERIALIZERS.set_password

    def _action(self, serializer):
        self.request.user.set_password(serializer.data['new_password'])
        self.request.user.save()
        with translation.override(self.request.user.preferred_language):
            send_mail(_("Password changed"),
                      _(
                          "Your password has been changed. "
                          f"If it happened without your desire - contact us by email support@{moses_settings.domain}."),
                      'noreply@' + moses_settings.DOMAIN, [self.request.user.email])
        if djoser_settings.LOGOUT_ON_PASSWORD_CHANGE:
            logout_user(self.request)

        return Response(status=status.HTTP_204_NO_CONTENT)


class RequestPhoneNumberConfirmPin(generics.GenericAPIView):
    serializer_class = ShortCustomUserSerializer

    def post(self, request):
        if (now() - request.user.last_phone_number_confirm_pin_sent).days > 0 and \
                (now() - request.user.last_phone_number_candidate_confirm_pin_sent).days > 0:
            request.user.send_phone_number_confirmation_sms()
            request.user.send_phone_number_candidate_confirmation_sms()
            return Response({})
        return Response({'non_field_errors': ['too_frequent_sms_request']}, status=status.HTTP_400_BAD_REQUEST)


class RequestEmailConfirmPin(generics.GenericAPIView):
    serializer_class = ShortCustomUserSerializer

    def post(self, request):
        request.user.send_email_confirmation_email()
        request.user.send_email_candidate_confirmation_email()
        return Response({})


class GetUserRoles(views.APIView):
    def get(self, request):
        query_set = Group.objects.filter(user=request.user)
        return Response(query_set.all().values())


class UserByPhoneOrEmail(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        phone_or_email = request.GET.get('value', None)
        user = CustomUser.objects.filter(Q(email=phone_or_email) | Q(phone_number=phone_or_email)).first()
        if user:
            return Response(ShortCustomUserSerializer(user).data)
        else:
            return Response({'non_field_errors': ['user_not_found']}, status=status.HTTP_404_NOT_FOUND)
