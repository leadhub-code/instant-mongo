from logging import basicConfig, DEBUG
from os import environ
from sys import stdout


if environ.get('LOG_TO_STDOUT'):
    basicConfig(
        format='%(asctime)s [%(process)d] %(name)-15s %(levelname)5s: %(message)s',
        level=DEBUG,
        stream=stdout)
