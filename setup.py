#!/usr/bin/env python
#
# Setup script for Django Evolution

from setuptools import setup, find_packages
from setuptools.command.test import test

from django_evolution import get_package_version, VERSION


def run_tests(*args):
    import os
    os.system('tests/runtests.py')

test.run_tests = run_tests


PACKAGE_NAME = 'django_evolution'

download_url = (
    'https://downloads.reviewboard.org/releases/django-evolution/%s.%s/' %
    (VERSION[0], VERSION[1]))


# Build the package
setup(
    name=PACKAGE_NAME,
    version=get_package_version(),
    license='BSD',
    description=('A database schema evolution tool for the Django web '
                 'framework.'),
    url='https://github.com/beanbaginc/django-evolution',
    author='Ben Khoo',
    author_email='khoobks@westnet.com.au',
    maintainer='Beanbag, Inc.',
    maintainer_email='reviewboard@googlegroups.com',
    download_url=download_url,
    packages=find_packages(exclude=['tests']),
    install_requires=[
        'Django>=1.6,<1.11.999',
    ],
    include_package_data=True,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Framework :: Django',
        'Framework :: Django :: 1.6',
        'Framework :: Django :: 1.7',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Framework :: Django :: 1.10',
        'Framework :: Django :: 1.11',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
