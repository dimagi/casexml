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
        'celery==3.0.15',
        'jsonobject-couchdbkit>=0.6.5.2',
        'couchforms==1.0.1',
        'couchexport',
        'decorator',
        'dimagi-utils>=1.0.8',
        'django==1.3.7',
        'requests==2.0.0',
        'django-digest',
        'lxml',
        'mock', # Actually a missing dimagi-utils dep?
        'receiver>=1.0.0',
        'requests==2.0.0',
        'restkit',
        'python-digest',
        'pytz',
        'simplejson',
        'Pillow==2.0.0',
        'unittest2', # Actually a missing dimagi-utils dep?
    ],
    tests_require = [
        'coverage',
        'django-coverage',    
    ],
    packages = find_packages(exclude=['*.pyc']),
    include_package_data=True
)

