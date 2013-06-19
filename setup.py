#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='casexml',
    version='1.0.0',
    description='Dimagi CaseXML for Django',
    author='Dimagi',
    author_email='dev@dimagi.com',
    url='http://www.dimagi.com/',
    install_requires = [
        'celery',    
        'couchdbkit',
        'couchforms>=1.0.0',
        'couchexport',
        'decorator',
        'dimagi-utils>=1.0.3',
        'django',
        'django-digest',    
        'lxml',
        'receiver>=1.0.0',
        'requests',
        'restkit',
        'python-digest',
        'pytz',
        'simplejson',
    ],
    tests_require = [
        'coverage',
        'django-coverage',    
    ],
    packages = find_packages(exclude=['*.pyc']),
    include_package_data=True
)

