#!/usr/bin/env python3

from pathlib import Path
from setuptools import setup, find_packages

here = Path(__file__).parent


with (here / 'README.md').open() as f:
    readme = f.read()


setup(
    name='instant-mongo',
    version='1.0.2',
    description='MongoDB runner for integration (and other) tests',
    long_description=readme,
    url='https://github.com/messa/instant-mongo',
    author='Petr Messner',
    author_email='petr.messner@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='instant MongoDB testing',
    packages=find_packages(exclude=['doc', 'tests']),
    install_requires=[
        'pymongo',
    ],

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        #'dev': ['check-manifest'],
        'test': ['pytest'],
    },
)
