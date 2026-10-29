# coding: utf-8
from __future__ import unicode_literals

from django.contrib import admin
from django.urls import path, include
from moses import urls
from moses.admin import OTPAdminAuthenticationForm

app_name = 'api'

admin.site.login_form = OTPAdminAuthenticationForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(urls, namespace='moses'))
]
