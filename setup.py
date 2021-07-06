from setuptools import setup

setup(zip_safe=False, install_requires=[
    'django',
    'djangorestframework-simplejwt',
    'djoser',
    'pyotp'
])
