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
from moses.serializers import GoogleSignInSerializer, GoogleCompleteRegistrationSerializer
from moses.services.google_auth import (
    verify_google_id_token,
    create_google_auth_temp_token,
    decode_google_auth_temp_token,
)


class GoogleSignInView(APIView):
    """
    POST /moses/token/google/

    Step 1 of Google Sign-In.
    Accepts a Google ID token and domain.

    If user exists (by email + site): links Google account, returns JWT tokens.
    If user is new: returns a temporary token for completing registration.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleSignInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_token_str = serializer.validated_data['id_token']
        domain = serializer.validated_data['domain']

        google_claims = verify_google_id_token(id_token_str)

        google_email = google_claims.get('email', '')
        google_sub = google_claims.get('sub', '')

        if not google_email:
            raise CustomAPIException({
                'id_token': [KwargsError(code=error_codes.INVALID_GOOGLE_ID_TOKEN)]
            })

        site = Site.objects.get(domain=domain)

        try:
            user = CustomUser.objects.get(site=site, email=google_email)
        except CustomUser.DoesNotExist:
            user = None

        if user is not None:
            if not user.google_sub:
                user.google_sub = google_sub
                user.save(update_fields=['google_sub'])

            refresh = RefreshToken.for_user(user)
            return Response({
                'status': 'authenticated',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        else:
            temp_token = create_google_auth_temp_token(google_claims)
            return Response({
                'status': 'phone_required',
                'google_auth_token': temp_token,
                'email': google_email,
                'first_name': google_claims.get('given_name', ''),
                'last_name': google_claims.get('family_name', ''),
            })


class GoogleCompleteRegistrationView(APIView):
    """
    POST /moses/token/google/complete/

    Step 2 of Google Sign-In (new users only).
    Accepts the temporary google_auth_token, phone_number, and domain.
    Creates the user and returns JWT tokens.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleCompleteRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['google_auth_token']
        phone_number = serializer.validated_data['phone_number']
        domain = serializer.validated_data['domain']

        payload = decode_google_auth_temp_token(token)

        google_sub = payload['google_sub']
        email = payload['email']
        first_name = payload.get('first_name', '')
        last_name = payload.get('last_name', '')

        site = Site.objects.get(domain=domain)

        if CustomUser.objects.filter(site=site, email=email).exists():
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
                    google_sub=google_sub,
                    is_email_confirmed=True,
                    preferred_language=moses_settings.DEFAULT_LANGUAGE,
                )
        except IntegrityError:
            raise CustomAPIException({
                '': [KwargsError(
                    code=error_codes.EMAIL_ALREADY_REGISTERED_ON_DOMAIN,
                    kwargs={'email': email}
                )]
            })

        refresh = RefreshToken.for_user(user)
        return Response({
            'status': 'authenticated',
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)
