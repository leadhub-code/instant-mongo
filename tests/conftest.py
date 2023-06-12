import logging
import sys


logging.basicConfig(
    format='%(asctime)s [%(process)d] %(name)-15s %(levelname)5s: %(message)s',
    level=logging.DEBUG,
    stream=sys.stdout)
