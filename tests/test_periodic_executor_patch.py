'''
Pymongo uses a background thread to periodically check if the server is alive.
After mongo client is closed, it takes some additional time to shut down that background thread.
This library contains a monkey-patch to speed up that shutdown.
This file tests whether the patch works as expected.
'''

from subprocess import check_call
from logging import getLogger
import sys
from textwrap import dedent
from time import time
# It would be better to use monotonic time, but I'm not sure if the monotonic clock
# value is preserved across different processes.


logger = getLogger(__name__)


def test_instant_mongo_duration(tmp_path):
    (tmp_path / 'test_script.py').write_text(test_script)
    # Looks like we need to run the test code in an entirely separate process.
    # Python module multiprocessing doesn't isolate enough apparently.
    cmd = [sys.executable, str(tmp_path / 'test_script.py'), str(tmp_path)]
    # Run the test 3 times to make sure the results are consistent with different sleep intervals.
    for i in range(3):
        logger.debug('Running %s', ' '.join(cmd))
        t0 = time()
        check_call(cmd)
        t2 = time()
        t1 = float((tmp_path / 'timestamp').read_text())
        logger.debug('Total process duration: %.3f s', t2 - t0)
        logger.debug('Shutdown duration: %.3f s', t2 - t1)
        # without the periodic executor patch the shutdown duration is about 0.5 s
        assert t2 - t1 < 0.1


test_script = dedent('''
    from argparse import ArgumentParser
    from instant_mongo import InstantMongoDB
    from logging import getLogger, basicConfig, DEBUG
    from pathlib import Path
    from random import random
    from time import time, sleep

    logger = getLogger('test_script')

    def main():
        p = ArgumentParser()
        p.add_argument('tmp_path')
        args = p.parse_args()
        basicConfig(
            format='%(asctime)s [%(process)d] %(name)-15s %(levelname)5s: %(message)s',
            level=DEBUG)
        logger.debug('inside instant_mongo_example - before with-block')
        with InstantMongoDB(args.tmp_path) as im:
            logger.debug('inside instant_mongo_example - at the start of with-block')
            client = im.get_client()
            client['testdb']['testcoll'].insert_one({'foo': 'bar'})
            # We might hit the background thread check time closely, so add some sleep here
            # to make sure the patch works for all program durations.
            sleep(random() * 0.5)
            client['testdb']['testcoll'].insert_one({'foo': 'baz'})
            logger.debug('inside instant_mongo_example - at the end of with-block')
            (Path(args.tmp_path) / 'timestamp').write_text(str(time()))
        logger.debug('inside instant_mongo_example - after with-block')

    if __name__ == '__main__':
        main()
''')
