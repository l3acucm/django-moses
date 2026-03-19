from django.contrib.sites.models import Site
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from moses.common import error_codes
from moses.common.exceptions import CustomAPIException, KwargsError
from moses.conf import settings as moses_settings
from moses.models import CustomUser
from moses.serializers import TelegramSignInSerializer, TelegramCompleteRegistrationSerializer
from moses.services.telegram_auth import (
    verify_telegram_auth_data,
    create_telegram_auth_temp_token,
    decode_telegram_auth_temp_token,
)


class TelegramSignInView(APIView):
    """
    POST /moses/token/telegram/

    Step 1 of Telegram Sign-In.
    Accepts Telegram Login Widget auth data and domain.

    Auth data fields: id, first_name, last_name, username, photo_url, auth_date, hash.

    If user exists (by telegram_id + site): returns JWT tokens.
    If user is new: returns a temporary token for completing registration.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TelegramSignInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        auth_data = serializer.validated_data['auth_data']
        domain = serializer.validated_data['domain']

        verified_data = verify_telegram_auth_data(auth_data)

        telegram_id = str(verified_data['id'])

        site = Site.objects.get(domain=domain)

        try:
            user = CustomUser.objects.get(site=site, telegram_id=telegram_id)
        except CustomUser.DoesNotExist:
            user = None

        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                'status': 'authenticated',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        else:
            temp_token = create_telegram_auth_temp_token(verified_data)
            return Response({
                'status': 'phone_required',
                'telegram_auth_token': temp_token,
                'first_name': verified_data.get('first_name', ''),
                'last_name': verified_data.get('last_name', ''),
                'username': verified_data.get('username', ''),
            })


class TelegramCompleteRegistrationView(APIView):
    """
    POST /moses/token/telegram/complete/

    Step 2 of Telegram Sign-In (new users only).
    Accepts the temporary telegram_auth_token, phone_number, email, and domain.
    Creates the user and returns JWT tokens.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TelegramCompleteRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['telegram_auth_token']
        phone_number = serializer.validated_data['phone_number']
        email = serializer.validated_data.get('email', '')
        domain = serializer.validated_data['domain']

        payload = decode_telegram_auth_temp_token(token)

        telegram_id = payload['telegram_id']
        first_name = payload.get('first_name', '')
        last_name = payload.get('last_name', '')

        site = Site.objects.get(domain=domain)

        if email and CustomUser.objects.filter(site=site, email=email).exists():
            raise CustomAPIException({
                'email': [
                    KwargsError(
                        kwargs={'email': email},
                        code=error_codes.EMAIL_ALREADY_REGISTERED_ON_DOMAIN
                    )
                ]
            })

        if CustomUser.objects.filter(site=site, phone_number=phone_number).exists():
            raise CustomAPIException({
                'phone_number': [
                    KwargsError(
                        kwargs={'phone_number': phone_number},
                        code=error_codes.PHONE_NUMBER_ALREADY_REGISTERED_ON_DOMAIN
                    )
                ]
            })

        if not moses_settings.PHONE_NUMBER_VALIDATOR(phone_number):
            raise CustomAPIException({
                'phone_number': [
                    KwargsError(
                        kwargs={'phone_number': phone_number},
                        code=error_codes.INVALID_PHONE_NUMBER
                    )
                ]
            })

        try:
            with transaction.atomic():
                user = CustomUser.objects.create_user(
                    phone_number=phone_number,
                    password=None,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    site=site,
                    telegram_id=telegram_id,
                    preferred_language=moses_settings.DEFAULT_LANGUAGE,
                )
        except IntegrityError:
            raise CustomAPIException({
                '': [KwargsError(
                    code=error_codes.PHONE_NUMBER_ALREADY_REGISTERED_ON_DOMAIN,
                    kwargs={'phone_number': phone_number}
                )]
            })

        refresh = RefreshToken.for_user(user)
        return Response({
            'status': 'authenticated',
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)
