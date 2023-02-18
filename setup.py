from setuptools import setup, find_packages

setup(zip_safe=False, install_requires=[
    'django',
    'djangorestframework-simplejwt',
    'djoser @ https://github.com/sunscrapers/djoser/',
    'pyotp'
], packages=find_packages(exclude=['test_project']))
