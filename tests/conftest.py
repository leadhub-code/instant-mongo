import logging
import sys


logging.basicConfig(
    format='%(asctime)s %(name)s %(levelname)5s: %(message)s',
    level=logging.DEBUG,
    stream=sys.stdout)
