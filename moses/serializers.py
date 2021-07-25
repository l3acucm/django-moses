from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions as django_exceptions
from django.db import IntegrityError, transaction
from django.utils.translation import ugettext as _
from djoser import constants
from guardian.shortcuts import get_perms
from rest_framework import serializers, exceptions
from rest_framework.fields import SerializerMethodField, CharField
from rest_framework.serializers import raise_errors_on_nested_writes, ModelSerializer, Serializer
from rest_framework.utils import model_meta
from rest_framework_simplejwt.serializers import TokenObtainSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from moses.models import CustomUser
from django.conf import settings
from moses.conf import settings as moses_settings


class PinSerializer(Serializer):
    pin = CharField()
    candidate_pin = CharField(required=False)


class GroupSerializer(ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'


class StaffSerializer(ModelSerializer):
    groups = SerializerMethodField()

    def get_groups(self, obj):
        return GroupSerializer(obj.groups.filter(name__startswith=self.get_context()), many=True).data

    def get_permissions(self, obj):
        return get_perms(obj, self.context['method'])

    class Meta:
        model = CustomUser
        fields = 'first_name', 'last_name', 'email', 'phone_number', 'permissions', 'id', 'groups'


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)

    default_error_messages = {'email_not_found': constants.Messages.EMAIL_NOT_FOUND,
                              'phone_number_not_found': _('User with given phone number does not exist.')}

    def validate_email(self, value):
        users = self.context['view'].get_users_by_email(value)
        if not users.exists():
            self.fail('email_not_found')
        else:
            return value

    def validate_phone_number(self, value):
        users = self.context['view'].get_users_by_phone_number(value)
        if not users.exists():
            self.fail('phone_number_not_found')
        else:
            return value


class ShortCustomUserSerializer(serializers.ModelSerializer):
    income_subscription = serializers.BooleanField(read_only=True)
    outcome_subscription = serializers.BooleanField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'userpic', 'outcome_subscription', 'income_subscription']
        read_only_fields = ['id', 'first_name', 'last_name', 'userpic', 'income_subscription',
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

    def validate(self, attrs):
        if 'phone_number' in attrs and not moses_settings.PHONE_NUMBER_VALIDATOR(attrs['phone_number']):
            raise serializers.ValidationError({
                'phone_number': _('Incorrect phone number')
            })
        return attrs

    def update(self, instance, validated_data):
        raise_errors_on_nested_writes('update', self, validated_data)
        info = model_meta.get_field_info(instance)
        if 'phone_number' in validated_data:
            _phone_number = validated_data.pop('phone_number')
            if _phone_number == instance.phone_number:
                instance.phone_number_candidate = ''
                instance.phone_number_confirm_pin = 0
                instance.phone_number_candidate_confirm_pin = 0
                instance.phone_number_confirm_attempts = 0
                instance.save()
            elif _phone_number != (instance.phone_number_candidate or instance.phone_number):
                if instance.is_phone_number_confirmed:
                    instance.phone_number_candidate = _phone_number
                    instance.phone_number_confirm_attempts = 0
                    instance.save()
                    instance.send_phone_number_confirmation_sms(generate_new=True)
                    instance.send_phone_number_candidate_confirmation_sms(generate_new=True)
                else:
                    instance.phone_number_confirm_attempts = 0
                    instance.save()
                    instance.send_phone_number_confirmation_sms(generate_new=True)
        if 'email' in validated_data:
            _email = validated_data.pop('email')
            if _email == instance.email:
                instance.email_candidate = ''
                instance.email_confirm_pin = 0
                instance.email_candidate_confirm_pin = 0
                instance.email_confirm_attempts = 0
                instance.save()
            elif _email != (instance.email_candidate or instance.email):
                if instance.is_email_confirmed:
                    instance.email_candidate = _email
                    instance.email_confirm_attempts = 0
                    instance.save()
                    instance.send_email_confirmation_email(generate_new=True)
                    instance.send_email_candidate_confirmation_email(generate_new=True)
                else:
                    instance.email_confirm_attempts = 0
                    instance.save()
                    instance.send_email_confirmation_email(generate_new=True)
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                field = getattr(instance, attr)
                field.set(value)
            else:
                setattr(instance, attr, value)
        instance.save()
        return instance

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'userpic',
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


class CustomUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        style={'input_type': 'password'},
        write_only=True
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
            'preferred_language'
        ]

    def validate(self, attrs):
        if not moses_settings.PHONE_NUMBER_VALIDATOR(attrs['phone_number']):
            raise serializers.ValidationError({
                'phone_number': _('Incorrect phone number')
            })
        if 'email' not in attrs or CustomUser.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({
                'email': _('User with this email already exists')
            })
        user_attrs = {k: v for k, v in attrs.items() if k != 'inviter_id'}
        user = CustomUser(**user_attrs)
        password = attrs.get('password')
        try:
            validate_password(password, user)
        except django_exceptions.ValidationError as e:
            serializer_error = serializers.as_serializer_error(e)
            raise serializers.ValidationError({
                'password': serializer_error['non_field_errors']
            })
        return attrs

    def create(self, validated_data):
        try:
            user = self.perform_create(validated_data)
        except IntegrityError as e:
            self.fail('cannot_create_user')
        return user

    def perform_create(self, validated_data):
        with transaction.atomic():
            user = CustomUser.objects.create_user(**validated_data)
            user.preferred_language = 1
        return user


class TokenObtainPairSerializer(TokenObtainSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['otp'] = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    @classmethod
    def get_token(cls, user):
        return RefreshToken.for_user(user)

    def validate(self, attrs):

        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            'password': attrs['password'],
            'otp': attrs.get('otp'),
            'ip': self.context['request'].META['HTTP_CF_CONNECTING_IP'] if not settings.DEBUG else None
        }
        try:
            authenticate_kwargs['request'] = self.context['request']
        except KeyError:
            pass

        self.user = authenticate(**authenticate_kwargs)

        if self.user is None or not self.user.is_active:
            raise exceptions.AuthenticationFailed(
                self.error_messages['no_active_account'],
                'no_active_account',
            )

        data = {}

        refresh = self.get_token(self.user)

        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        return data
