from setuptools import setup, find_packages

setup(zip_safe=False, install_requires=[
    'django',
    'djangorestframework-simplejwt',
    'djoser @ git+ssh://git@github.com/sunscrapers/djoser.git',
    'pyotp'
], packages=find_packages(exclude=['test_project']))
