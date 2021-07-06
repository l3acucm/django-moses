from setuptools import setup

setup(zip_safe=False, setup_requires=[
    'djangorestframework-simplejwt',
    'djoser',
    'pyotp'
])
