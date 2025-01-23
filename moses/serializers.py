from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.contrib.sites.models import Site
from django.core import exceptions as django_exceptions
from django.core.validators import EmailValidator
from django.db import IntegrityError, transaction
from django.db.models import Q
from djoser import constants
from rest_framework import serializers, status
from rest_framework.fields import CharField
from rest_framework.serializers import raise_errors_on_nested_writes, ModelSerializer, Serializer
from rest_framework.utils import model_meta
from rest_framework_simplejwt.serializers import TokenObtainSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from moses.common import error_codes
from moses.common.exceptions import CustomAPIException, KwargsError
from moses.conf import settings as moses_settings
from moses.enums import Credential
from moses.models import CustomUser
from moses.services.credentials_confirmation import send_credential_confirmation_code


class PinSerializer(Serializer):
    pin = CharField()
    candidate_pin = CharField(required=False)


class MFASerializer(Serializer):
    otp = CharField()
    secret_key = CharField()
    action = CharField(required=False)


class GroupSerializer(ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)

    def validate_email(self, value):
        users = self.context['view'].get_users_by_email(value)
        if not users.exists():
            raise CustomAPIException({
                'email': [
                    KwargsError(error_codes.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN)
                ]
            })
        else:
            return value

    def validate_phone_number(self, value):
        users = self.context['view'].get_users_by_phone_number(value)
        if not users.exists():
            raise CustomAPIException({
                'phone_number': [
                    KwargsError(error_codes.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN)
                ]
            })
        else:
            return value


class ShortCustomUserSerializer(serializers.ModelSerializer):
    income_subscription = serializers.BooleanField(read_only=True)
    outcome_subscription = serializers.BooleanField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'outcome_subscription', 'income_subscription']
        read_only_fields = ['id', 'first_name', 'last_name', 'income_subscription',
                            'outcome_subscription']


class PublicCustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'first_name',
            'last_name',
        ]


class PrivateCustomUserSerializer(serializers.ModelSerializer):
    is_mfa_enabled = serializers.SerializerMethodField()

    def get_is_mfa_enabled(self, obj):
        return len(obj.mfa_secret_key) > 0

    def update(self, user, validated_data):
        raise_errors_on_nested_writes('update', self, validated_data)
        info = model_meta.get_field_info(user)
        if (phone_number := validated_data.get('phone_number')) is not None:
            if phone_number != (user.phone_number_candidate or user.phone_number):
                if user.is_phone_number_confirmed:
                    user.phone_number_candidate = phone_number
                    user.phone_number_confirm_attempts = 0
                    user.save()
                    send_credential_confirmation_code(
                        user,
                        Credential.PHONE_NUMBER,
                        candidate=False,
                        generate_new=True,
                        ignore_frequency_limit=True
                    )
                    send_credential_confirmation_code(
                        user,
                        Credential.PHONE_NUMBER,
                        candidate=True,
                        generate_new=True,
                        ignore_frequency_limit=True
                    )
                else:
                    user.phone_number = phone_number
                    user.phone_number_confirm_attempts = 0
                    user.save()
                    send_credential_confirmation_code(
                        user,
                        Credential.PHONE_NUMBER,
                        candidate=False,
                        generate_new=True,
                        ignore_frequency_limit=True
                    )
            del validated_data['phone_number']
        if 'email' in validated_data:
            _email = validated_data.pop('email')
            if _email == user.email:
                user.email_candidate = ''
                user.email_confirm_pin = 0
                user.email_candidate_confirm_pin = 0
                user.email_confirm_attempts = 0
                user.save()
            elif _email != (user.email_candidate or user.email):
                if user.is_email_confirmed:
                    user.email_candidate = _email
                    user.email_confirm_attempts = 0
                    user.save()
                    send_credential_confirmation_code(user, Credential.EMAIL, candidate=False, generate_new=True)
                    send_credential_confirmation_code(user, Credential.EMAIL, candidate=True, generate_new=True)
                else:
                    user.email = _email
                    user.email_confirm_attempts = 0
                    user.save()
                    send_credential_confirmation_code(user, Credential.EMAIL, generate_new=True)
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                field = getattr(user, attr)
                field.set(value)
            else:
                setattr(user, attr, value)
        user.save()
        self.instance = user
        return user

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'email',
            'email_candidate',
            'first_name',
            'last_name',
            'phone_number',
            'phone_number_candidate',
            'is_phone_number_confirmed',
            'is_email_confirmed',
            'preferred_language',
            'is_mfa_enabled'
        ]


def site_with_domain_exists(value):
    if not Site.objects.filter(domain=value).exists():
        raise CustomAPIException(
            {
                'domain': [
                    KwargsError(
                        kwargs={'domain': value},
                        code=error_codes.SITE_WITH_DOMAIN_DOES_NOT_EXIST)
                ]
            }
        )


class CustomUserCreateSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(validators=[moses_settings.PHONE_NUMBER_VALIDATOR])
    email = serializers.CharField(validators=[EmailValidator])
    domain = serializers.CharField(validators=[site_with_domain_exists], write_only=True)
    password = serializers.CharField(
        style={'input_type': 'password'},
        write_only=True,
        validators=[validate_password]
    )
    default_error_messages = {
        'cannot_create_user': constants.Messages.CANNOT_CREATE_USER_ERROR,
    }

    class Meta:
        model = CustomUser
        fields = [
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'password',
            'preferred_language',
            'domain'
        ]

    def validate(self, attrs):
        if 'email' not in attrs or CustomUser.objects.filter(
                site__domain=attrs['domain'],
                email=attrs['email']
        ).exists():
            raise CustomAPIException(
                {
                    'email': [
                        KwargsError(
                            kwargs={'email': attrs.get('email')},
                            code=error_codes.EMAIL_ALREADY_REGISTERED_ON_DOMAIN)
                    ]
                }
            )
        if 'phone_number' not in attrs or CustomUser.objects.filter(
                site__domain=attrs['domain'],
                phone_number=attrs['phone_number']
        ).exists():
            raise CustomAPIException(
                {
                    'phone_number': [
                        KwargsError(
                            kwargs={'phone_number': attrs.get('phone_number')},
                            code=error_codes.PHONE_NUMBER_ALREADY_REGISTERED_ON_DOMAIN)
                    ]
                }
            )
        elif not moses_settings.PHONE_NUMBER_VALIDATOR(attrs['phone_number']):
            raise CustomAPIException(
                {
                    'phone_number': [
                        KwargsError(
                            kwargs={'phone_number': attrs.get('phone_number')},
                            code=error_codes.INVALID_PHONE_NUMBER)
                    ]
                }
            )

        attrs['site'] = Site.objects.get(domain=attrs.pop('domain'))
        user_attrs = {k: v for k, v in attrs.items() if k != 'inviter_id'}
        user = CustomUser(**user_attrs)
        return attrs

    def create(self, validated_data):
        try:
            user = self.perform_create(validated_data)
        except IntegrityError as e:
            self.fail('cannot_create_user')
        return user

    def perform_create(self, validated_data):
        with transaction.atomic():
            if 'preferred_language' not in validated_data:
                validated_data['preferred_language'] = moses_settings.DEFAULT_LANGUAGE
            user = CustomUser.objects.create_user(**validated_data)
        return user


class TokenObtainPairSerializer(TokenObtainSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['otp'] = serializers.CharField(required=False, allow_blank=True, allow_null=True)
        self.fields['domain'] = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    @classmethod
    def get_token(cls, user):
        return RefreshToken.for_user(user)

    def validate(self, attrs):
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            'password': attrs['password'],
            'otp': attrs.get('otp'),
            'domain': attrs.get('domain')
        }
        try:
            authenticate_kwargs['request'] = self.context['request']
        except KeyError:
            pass

        self.user = authenticate(**authenticate_kwargs)

        if self.user is None or not self.user.is_active:
            raise CustomAPIException(
                {
                    '': [
                        KwargsError(
                            kwargs={},
                            code=error_codes.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN)
                    ]
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        data = {}

        refresh = self.get_token(self.user)

        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        return data


class PasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(style={"input_type": "password"})

    def validate(self, attrs):
        user = getattr(self, "user", None) or self.context["request"].user
        # why assert? There are ValidationError / fail everywhere
        assert user is not None

        try:
            validate_password(attrs["new_password"], user)
        except django_exceptions.ValidationError as e:
            raise CustomAPIException(
                {
                    'new_password': [
                        KwargsError(
                            kwargs={},
                            code=error_codes.INVALID_PASSWORD)
                    ]
                }
            )
        return super().validate(attrs)


class ResetPasswordSerializer(serializers.Serializer):
    credential = serializers.CharField()
    domain = serializers.CharField()

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        if (user := CustomUser.objects.filter(
                Q(phone_number=validated_data['credential'], is_phone_number_confirmed=True) | Q(
                    email=validated_data['credential'], is_email_confirmed=True),
                site__domain=validated_data['domain'],
        ).first()) is None:
            raise CustomAPIException(
                {
                    'credential': [
                        KwargsError(
                            kwargs={'credential': attrs.get('credential')},
                            code=error_codes.USER_WITH_PROVIDED_CREDENTIALS_DOES_NOT_REGISTERED_ON_SPECIFIED_DOMAIN)
                    ]
                }
            )
        else:
            self.user = user
        return validated_data


class ConfirmResetPasswordSerializer(PasswordSerializer):
    credential = serializers.CharField()
    domain = serializers.CharField()
    code = serializers.IntegerField()

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        if (user := CustomUser.objects.filter(
                Q(phone_number=validated_data['credential']) | Q(email=validated_data['credential']),
                site__domain=validated_data['domain'],
        ).first()) is not None:

            if user.password_reset_code != validated_data['code']:
                raise CustomAPIException(
                    {
                        'code': [
                            KwargsError(
                                kwargs={},
                                code=error_codes.INVALID_CONFIRMATION_CODE)
                        ]
                    }
                )
        else:
            raise CustomAPIException(
                {
                    'code': [
                        KwargsError(
                            kwargs={},
                            code=error_codes.INVALID_CONFIRMATION_CODE)
                    ]
                }
            )
        self.user = user
        return validated_data
