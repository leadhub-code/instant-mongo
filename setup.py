#!/usr/bin/env python

from pathlib import Path
from setuptools import setup, find_packages

here = Path(__file__).resolve().parent
readme = (here / 'README.md').open(encoding='UTF-8').read()


setup(
    name='instant-mongo',
    version='0.0.4',
    description='Launch Mongodb instance for dev and testing',
    long_description=readme,
    url='https://github.com/messa/instant-mongo',
    author='Petr Messner',
    author_email='petr.messner@gmail.com',
    license='MIT',
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],
    keywords='MongoDB mongo testing',
    packages=find_packages(exclude=['test*']),
    install_requires=['pymongo'],
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'instant-mongo=instant_mongo:main',
        ],
    },
)
