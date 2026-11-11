from django.test import TestCase
from rest_framework.response import Response

from moses.decorators import phone_number_confirmed_required
from moses.models import CustomUser
from test_project.app_for_tests import drf_request_factory


class _DummyView:
    @phone_number_confirmed_required
    def action(self, request):
        return Response({'ok': True})


class PhoneNumberConfirmedRequiredTestCase(TestCase):
    fixtures = ['login']

    def setUp(self):
        self.user = CustomUser.objects.get(id=1)
        self.view = _DummyView()

    def test_runs_view_when_phone_confirmed(self):
        self.user.is_phone_number_confirmed = True
        request = drf_request_factory.post('/')
        request.user = self.user
        response = self.view.action(request)
        self.assertEqual(response.status_code, 200)

    def test_blocks_view_when_phone_not_confirmed(self):
        self.user.is_phone_number_confirmed = False
        request = drf_request_factory.post('/')
        request.user = self.user
        with self.assertRaises(Exception) as ctx:
            self.view.action(request)
        self.assertEqual(ctx.exception.errors_repr[''][0]['error_code'], 'phone_number_not_confirmed')
