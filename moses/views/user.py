import base64
import random
import string

import pyotp
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import translation
from django.utils.timezone import now
from django.utils.translation import gettext as _
from djoser import signals, utils
from djoser.compat import get_user_email
from djoser.conf import settings as djoser_settings
from djoser.utils import logout_user
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from moses import errors
from moses.conf import settings as moses_settings
from moses.decorators import otp_required
from moses.models import CustomUser, Credential
from moses.serializers import ShortCustomUserSerializer

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = djoser_settings.SERIALIZERS.user
    queryset = User.objects.all()
    permission_classes = djoser_settings.PERMISSIONS.user
    token_generator = default_token_generator
    lookup_field = djoser_settings.USER_ID_FIELD

    def permission_denied(self, request, **kwargs):
        if (
                djoser_settings.HIDE_USERS
                and request.user.is_authenticated
                and self.action in ["update", "partial_update", "list", "retrieve"]
        ):
            raise NotFound()
        super().permission_denied(request, **kwargs)

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        if djoser_settings.HIDE_USERS and self.action == "list" and not user.is_staff:
            queryset = queryset.filter(pk=user.pk)
        return queryset

    def get_permissions(self):
        if self.action == "create":
            self.permission_classes = djoser_settings.PERMISSIONS.user_create
        elif self.action == "resend_activation":
            self.permission_classes = djoser_settings.PERMISSIONS.password_reset
        elif self.action == "list":
            self.permission_classes = djoser_settings.PERMISSIONS.user_list
        elif self.action == "reset_password":
            self.permission_classes = djoser_settings.PERMISSIONS.password_reset
        elif self.action == "reset_password_confirm":
            self.permission_classes = djoser_settings.PERMISSIONS.password_reset_confirm
        elif self.action == "set_password":
            self.permission_classes = djoser_settings.PERMISSIONS.set_password
        elif self.action in ("mfa_status", "credential_availability"):
            self.permission_classes = []
        elif self.action == "destroy" or (
                self.action == "me" and self.request and self.request.method == "DELETE"
        ):
            self.permission_classes = djoser_settings.PERMISSIONS.user_delete
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            if djoser_settings.USER_CREATE_PASSWORD_RETYPE:
                return djoser_settings.SERIALIZERS.user_create_password_retype
            return djoser_settings.SERIALIZERS.user_create
        elif self.action == "destroy" or (
                self.action == "me" and self.request and self.request.method == "DELETE"
        ):
            return djoser_settings.SERIALIZERS.user_delete
        elif self.action == "activation":
            return djoser_settings.SERIALIZERS.activation
        elif self.action == "resend_activation":
            return djoser_settings.SERIALIZERS.password_reset
        elif self.action == "reset_password":
            return djoser_settings.SERIALIZERS.password_reset
        elif self.action == "reset_password_confirm":
            if djoser_settings.PASSWORD_RESET_CONFIRM_RETYPE:
                return djoser_settings.SERIALIZERS.password_reset_confirm_retype
            return djoser_settings.SERIALIZERS.password_reset_confirm
        elif self.action == "set_password":
            if djoser_settings.SET_PASSWORD_RETYPE:
                return djoser_settings.SERIALIZERS.set_password_retype
            return djoser_settings.SERIALIZERS.set_password
        elif self.action == "set_username":
            if djoser_settings.SET_USERNAME_RETYPE:
                return djoser_settings.SERIALIZERS.set_username_retype
            return djoser_settings.SERIALIZERS.set_username
        elif self.action == "reset_username":
            return djoser_settings.SERIALIZERS.username_reset
        elif self.action == "reset_username_confirm":
            if djoser_settings.USERNAME_RESET_CONFIRM_RETYPE:
                return djoser_settings.SERIALIZERS.username_reset_confirm_retype
            return djoser_settings.SERIALIZERS.username_reset_confirm
        elif self.action == "me":
            return djoser_settings.SERIALIZERS.current_user

        return self.serializer_class

    def get_instance(self):
        return self.request.user

    def perform_create(self, serializer, *args, **kwargs):
        user = serializer.save(*args, **kwargs)
        signals.user_registered.send(
            sender=self.__class__, user=user, request=self.request
        )

        context = {"user": user}
        to = [get_user_email(user)]
        if djoser_settings.SEND_ACTIVATION_EMAIL:
            djoser_settings.EMAIL.activation(self.request, context).send(to)
        elif djoser_settings.SEND_CONFIRMATION_EMAIL:
            djoser_settings.EMAIL.confirmation(self.request, context).send(to)

    def perform_update(self, serializer, *args, **kwargs):
        super().perform_update(serializer, *args, **kwargs)
        user = serializer.instance
        signals.user_updated.send(
            sender=self.__class__, user=user, request=self.request
        )

        # should we send activation email after update?
        if djoser_settings.SEND_ACTIVATION_EMAIL and not user.is_active:
            context = {"user": user}
            to = [get_user_email(user)]
            djoser_settings.EMAIL.activation(self.request, context).send(to)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        if instance == request.user:
            utils.logout_user(self.request)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["get", "put", "patch", "delete"], detail=False)
    def me(self, request, *args, **kwargs):
        self.get_object = self.get_instance
        if request.method == "GET":
            return self.retrieve(request, *args, **kwargs)
        elif request.method == "PUT":
            return self.update(request, *args, **kwargs)
        elif request.method == "PATCH":
            return self.partial_update(request, *args, **kwargs)
        elif request.method == "DELETE":
            return self.destroy(request, *args, **kwargs)

    @action(["post"], detail=False)
    def activation(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        user.is_active = True
        user.save()

        signals.user_activated.send(
            sender=self.__class__, user=user, request=self.request
        )

        if djoser_settings.SEND_CONFIRMATION_EMAIL:
            context = {"user": user}
            to = [get_user_email(user)]
            djoser_settings.EMAIL.confirmation(self.request, context).send(to)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["post"], detail=False)
    def resend_activation(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.get_user(is_active=False)

        if not djoser_settings.SEND_ACTIVATION_EMAIL or not user:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        context = {"user": user}
        to = [get_user_email(user)]
        djoser_settings.EMAIL.activation(self.request, context).send(to)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["get"], detail=False)
    def credential_availability(self, request):
        kwargs = {'site__domain': request.GET.get('domain')}
        if (email := request.GET.get('email')) is not None:
            kwargs['email'] = email
        elif (phone_number := request.GET.get('phone_number')) is not None:
            kwargs['phone_number'] = phone_number
        return Response(
            {
                'result': not CustomUser.objects.filter(**kwargs).exists()
            },
            status=status.HTTP_200_OK
        )

    @action(["get"], detail=False)
    def mfa_status(self, request):
        u_qs = CustomUser.objects.filter(phone_number=request.GET.get('phone_number'), site__domain=request.GET.get('domain'))
        result = u_qs.exists() and bool(u_qs.first().mfa_secret_key)
        return Response({'result': result}, status=status.HTTP_200_OK)

    @action(["post"], detail=False)
    def set_password(self, request, *args, **kwargs):
        if not request.user.check_password(request.data.get('current_password')):
            return Response(
                {'current_password': [errors.INVALID_PASSWORD]},
                status=status.HTTP_400_BAD_REQUEST
            )

        self.request.user.set_password(request.data.get('new_password'))
        self.request.user.save()
        with translation.override(self.request.user.preferred_language):
            send_mail(_("Password changed"),
                      _(
                          "Your password has been changed. "
                          f"If it happened without your desire - contact us by email support@{djoser_settings.DOMAIN}."),
                      'noreply@' + djoser_settings.DOMAIN, [self.request.user.email])
        if djoser_settings.LOGOUT_ON_PASSWORD_CHANGE:
            logout_user(self.request)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["post"], detail=False)
    def reset_password(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.user.send_password_reset_code(serializer.data["credential"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["post"], detail=False)
    def reset_password_confirm(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.user.set_password(serializer.data["new_password"])
        if hasattr(serializer.user, "last_login"):
            serializer.user.last_login = now()
        serializer.user.save()

        if djoser_settings.PASSWORD_CHANGED_EMAIL_CONFIRMATION:
            context = {"user": serializer.user}
            to = [get_user_email(serializer.user)]
            djoser_settings.EMAIL.password_changed_confirmation(self.request, context).send(to)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["post"], detail=False)
    def set_username(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.request.user
        new_username = serializer.data["new_" + User.USERNAME_FIELD]

        setattr(user, User.USERNAME_FIELD, new_username)
        user.save()
        if djoser_settings.USERNAME_CHANGED_EMAIL_CONFIRMATION:
            context = {"user": user}
            to = [get_user_email(user)]
            djoser_settings.EMAIL.username_changed_confirmation(self.request, context).send(to)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["post"], detail=False)
    def reset_username(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.get_user()

        if user:
            context = {"user": user}
            to = [get_user_email(user)]
            djoser_settings.EMAIL.username_reset(self.request, context).send(to)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["get"], detail=False)
    def get_user_by_phone_number_or_email(self, request):
        phone_or_email = request.GET.get('value', None)
        user = CustomUser.objects.filter(Q(email=phone_or_email) | Q(phone_number=phone_or_email)).first()
        if user:
            return Response(ShortCustomUserSerializer(user).data)
        else:
            return Response({'non_field_errors': ['user_not_found']}, status=status.HTTP_404_NOT_FOUND)

    @action(["get"], detail=False)
    def get_user_roles(self, request):
        query_set = Group.objects.filter(user=request.user)
        return Response(query_set.all().values())

    @action(["get"], detail=False)
    def get_mfa_key(self, request):
        mfa_secret_key = base64.b32encode(
            bytes(''.join(random.choice(string.ascii_letters) for _ in range(100)).encode('utf-8'))).decode('utf-8')
        return Response(
            {
                'mfa_secret_key': mfa_secret_key,
                'mfa_url': pyotp.totp.TOTP(
                    mfa_secret_key.encode('utf-8')
                ).provisioning_uri(
                    f"{request.user.first_name} {request.user.last_name}",
                    moses_settings.DOMAIN
                )
            }
        )

    @action(["post"], detail=False)
    def enable_mfa(self, request):
        mfa_secret_key = request.data.get('mfa_secret_key')
        otp = request.headers.get('otp', '')
        if pyotp.totp.TOTP(mfa_secret_key.encode('utf-8')).verify(otp):
            request.user.mfa_secret_key = mfa_secret_key
            request.user.save()
            return Response(
                {
                    'success': 'mfa has been successfully disabled'
                }
            )
        return Response(
            {
                'non_field_errors': ['invalid_otp']
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    @otp_required
    @action(["post"], detail=False)
    def disable_mfa(self, request):
        request.user.mfa_secret_key = ''
        request.user.save()
        return Response(
            {
                'success': 'mfa has been successfully disabled'
            }
        )

    @action(["post"], detail=False)
    def request_phone_number_confirmation_pin(self, request):
        if request.user.last_phone_number_confirmation_pins_sent is None or (
                now() - request.user.last_phone_number_confirmation_pins_sent).seconds >= 60 * moses_settings.PHONE_NUMBER_CONFIRMATION_SMS_MINUTES_PERIOD:
            request.user.send_credential_confirmation_code(Credential.PHONE_NUMBER)
            request.user.send_credential_confirmation_code(Credential.PHONE_NUMBER, candidate=True)
            return Response({})
        return Response({'non_field_errors': ['too_frequent_sms_request']}, status=status.HTTP_400_BAD_REQUEST)

    @action(["post"], detail=False)
    def request_email_confirmation_pin(self, request):
        request.user.send_email_confirmation_email()
        request.user.send_email_candidate_confirmation_email()
        return Response({})

    @action(["post"], detail=False)
    def confirm_email(self, request):
        candidate_email = request.user.email_candidate
        confirmation_result = request.user.try_to_confirm_credential(
            Credential.EMAIL,
            request.data.get('pin', ''),
            request.data.get('candidate_pin', '')
        )
        if False not in confirmation_result:
            if candidate_email:
                with translation.override(request.user.preferred_language):
                    send_mail(
                        _("Email changed"),
                        _(f"Your email has been changed. If it happened without your desire - "
                          f"contact us by email support@{moses_settings.DOMAIN}."),
                        'noreply@' + moses_settings.DOMAIN, [candidate_email]
                    )
            return Response({'result': 'ok'})
        result = {}
        if confirmation_result[0] == False:
            result['pin'] = [errors.INCORRECT_CONFIRMATION_PIN]
        if confirmation_result[1] == False:
            result['candidate_pin'] = [errors.INCORRECT_CONFIRMATION_PIN]
        return Response(result, status.HTTP_400_BAD_REQUEST)

    @action(["post"], detail=False)
    def confirm_phone_number(self, request):
        candidate_phone_number = request.user.phone_number_candidate
        confirmation_result = request.user.try_to_confirm_credential(
            Credential.PHONE_NUMBER,
            request.data.get('pin', ''),
            request.data.get('candidate_pin', '')
        )
        if False not in confirmation_result:
            if candidate_phone_number:
                with translation.override(request.user.preferred_language):
                    send_mail(
                        _("Phone number changed"),
                        _(f"Your phone number has been changed. If it happened without your desire - "
                          f"contact us by email support@{moses_settings.DOMAIN}."),
                        'noreply@' + moses_settings.DOMAIN, [request.user.email]
                    )
            return Response(
                {
                    'success': True
                }
            )
        else:
            result = dict()
            if not confirmation_result[0]:
                result['pin'] = [errors.INCORRECT_CONFIRMATION_PIN]
            if not confirmation_result[1] and confirmation_result[1] is not None:
                result['candidate_pin'] = [errors.INCORRECT_CONFIRMATION_PIN]
            return Response(result, status=400)
