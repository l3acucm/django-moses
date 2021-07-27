# coding: utf-8
from __future__ import unicode_literals

from django.urls import path, include
from moses import urls

app_name = 'api'

urlpatterns = [
    path('', include(urls, namespace='moses'))
]
