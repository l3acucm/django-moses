import base64
import json

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

client = Client()

drf_request_factory = APIRequestFactory()


class APIClient:
    def __init__(self, namespace):
        from moses.views.token_obtain_pair import TokenObtainPairView
        from moses.views.user import UserViewSet
        self.create_user_view = UserViewSet.as_view({'post': 'create'})
        self.update_user_view = UserViewSet.as_view({'patch': 'me'})
        self.request_phone_number_confirmation_pin_view = UserViewSet.as_view(
            {'post': 'request_phone_number_confirmation_pin'})
        self.confirm_phone_number_view = UserViewSet.as_view({'post': 'confirm_phone_number'})
        self.confirm_email_view = UserViewSet.as_view({'post': 'confirm_email'})
        self.update_password_view = UserViewSet.as_view({'post': 'set_password'})
        self.enable_mfa_view = UserViewSet.as_view({'post': 'enable_mfa'})
        self.disable_mfa_view = UserViewSet.as_view({'post': 'disable_mfa'})
        self.login_view = TokenObtainPairView.as_view()
        self.reset_password_view = UserViewSet.as_view({'post': 'reset_password'})
        self.confirm_reset_password_view = UserViewSet.as_view({'post': 'reset_password_confirm'})
        self._namespace = namespace

    def create_user(self, phone_number, password, name, email, domain):
        request = drf_request_factory.post(
            reverse('moses:customuser-list'),
            json.dumps(
                {
                    'phone_number': phone_number,
                    'email': email,
                    'first_name': name,
                    'last_name': name,
                    'password': password,
                    'domain': domain
                }
            ),
            content_type='application/json',
        )
        response = self.create_user_view(request)
        if response.status_code == status.HTTP_201_CREATED:
            user = get_user_model().objects.get(
                site__domain=domain,
                email=response.data['email']
            )
        else:
            user = None
        return user, response

    def login(self, phone_number, password, domain):
        request = drf_request_factory.post(
            reverse('moses:token_obtain_pair'),
            json.dumps(
                {
                    'phone_number': phone_number,
                    'password': password,
                    'domain': domain
                }
            ),
            content_type='application/json',
        )
        response = self.login_view(request)
        if response.status_code == status.HTTP_200_OK:
            return get_user_model().objects.get(
                id=json.loads(base64.b64decode(response.data['access'].split('.')[1]))['user_id']
            ), response
        return None, response

    def request_phone_number_confirmation_pin(self, user):
        request = drf_request_factory.post(
            reverse('moses:customuser-request-phone-number-confirmation-pin'),
            json.dumps({
            }
            ),
            content_type='application/json',
        )
        force_authenticate(request, user)
        response = self.request_phone_number_confirmation_pin_view(request)
        return get_user_model().objects.get(id=user.id), response

    def reset_password(self, credential, domain):
        request = drf_request_factory.post(
            reverse('moses:customuser-reset-password'),
            json.dumps({'credential': credential, 'domain': domain}),
            content_type='application/json',
        )
        response = self.reset_password_view(request)
        return response

    def confirm_reset_password(self, credential, domain, code, password):
        request = drf_request_factory.post(
            reverse('moses:customuser-reset-password-confirm'),
            json.dumps({
                'credential': credential,
                'domain': domain,
                'code': code,
                'new_password': password
            }),
            content_type='application/json',
        )
        user = None
        response = self.confirm_reset_password_view(request)
        if response.status_code == 204:
            user = get_user_model().objects.get(site__domain=domain, phone_number=credential)
        return user, response

    def update_user(self, user, data):
        request = drf_request_factory.patch(
            reverse('moses:customuser-me'),
            json.dumps(data),
            content_type='application/json',
        )
        force_authenticate(request, user)
        response = self.update_user_view(request)
        return get_user_model().objects.get(id=user.id), response

    def confirm_phone_number(self, user, pin, candidate_pin=None):
        data = dict()
        if pin is not None:
            data['pin'] = pin
        if candidate_pin is not None:
            data['candidate_pin'] = candidate_pin
        request = drf_request_factory.post(
            reverse('moses:customuser-confirm-phone-number'),
            json.dumps(data),
            content_type='application/json',
        )
        force_authenticate(request, user)
        response = self.confirm_phone_number_view(request)
        return get_user_model().objects.get(id=user.id), response

    def confirm_email(self, user, pin=None, candidate_pin=None):
        data = {}
        if candidate_pin is not None:
            data['pin'] = pin
        if candidate_pin is not None:
            data['candidate_pin'] = candidate_pin
        request = drf_request_factory.post(
            reverse('moses:customuser-confirm-email'),
            json.dumps(data),
            content_type='application/json',
        )
        force_authenticate(request, user)
        response = self.confirm_email_view(request)
        return get_user_model().objects.get(id=user.id), response

    def update_password(self, user, current_password, new_password):
        request = drf_request_factory.post(
            reverse('moses:customuser-set-password'),
            json.dumps({
                'current_password': current_password,
                'new_password': new_password
            }),
            content_type='application/json'
        )
        force_authenticate(request, user)
        response = self.update_password_view(request)
        return get_user_model().objects.get(id=user.id), response

    def enable_mfa(self, user, key, otp):
        request = drf_request_factory.post(
            reverse('moses:customuser-enable-mfa'),
            json.dumps({'mfa_secret_key': key}),
            content_type='application/json',
            headers={'otp': otp}
        )
        force_authenticate(request, user)
        response = self.enable_mfa_view(request)
        return get_user_model().objects.get(id=user.id), response

    def disable_mfa(self, user, otp):
        request = drf_request_factory.post(
            reverse('moses:customuser-disable-mfa'),
            json.dumps({}),
            content_type='application/json',
            headers={'otp': otp}
        )
        force_authenticate(request, user)
        response = self.disable_mfa_view(request)
        return get_user_model().objects.get(id=user.id), response
