from setuptools import setup, find_packages

setup(zip_safe=False, install_requires=[
    'django',
    'djangorestframework-simplejwt',
    'djoser',
    'pyotp'
], packages=find_packages(exclude=['test_project']))
