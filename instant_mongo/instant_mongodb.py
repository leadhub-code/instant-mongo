from contextlib import contextmanager
import logging
from pathlib import Path
import pymongo
import subprocess
import threading

from .util import get_free_tcp_port, is_tcp_port_free, wait_for_accepting_tcp_conns

__short_name = 'instant_mongodb' if __name__ == 'instant_mongodb.instant_mongodb' else __name__

logger = logging.getLogger(__short_name)


class InstantMongoDB:
    '''
    Usage:

    with InstantMongoDB(data_dir='/tmp/data') as im:
        print(im.testdb.collection_names())

    The database is automatically stopped at the end of the with-block.

    Available attributes and methods:

    - im.mongodb_uri is 'mongodb://127.0.0.1:{port}'
    - im.client is pymongo.MongoClient(im.mongodb_uri)
    - im.testdb is im.client.testdb
    - im.drop_everything() drops all collections; intended for tests
    '''

    def __init__(self, data_dir, port=None, bind_ip='127.0.0.1', wired_tiger=True, wired_tiger_zlib=False, journal=True):
        self.logger = logger
        if isinstance(data_dir, Path):
            self.data_dir = data_dir
        elif isinstance(data_dir, str):
            self.data_dir = Path(data_dir)
        elif data_dir.__class__.__name__ == 'LocalPath':
            self.data_dir = Path(str(data_dir))
        else:
            raise Exception('data_dir must be str or pathlib.Path')
        self.port = port
        self.bind_ip = bind_ip
        self.mongod_cmd = 'mongod'
        self.wired_tiger = wired_tiger
        self.wired_tiger_cache_size_gb = 1
        self.wired_tiger_zlib = wired_tiger_zlib
        self.journal = journal
        self._mongod_process = None
        self._stdout_thread = None
        self._stderr_thread = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        if not self.data_dir.is_dir():
            self.logger.info('Creating directory %s', self.data_dir)
            self.data_dir.mkdir()
        if not self.port:
            self.port = get_free_tcp_port()
        if not is_tcp_port_free(self.port):
            raise Exception('Port %s is not available' % self.port)
        assert self.port
        if self._mongod_process:
            raise Exception('Already started')
        cmd = [
            self.mongod_cmd,
            '--port', str(self.port),
            '--bind_ip', self.bind_ip,
            '--nounixsocket',
            '--dbpath', str(self.data_dir),
            '--smallfiles']
        if self.wired_tiger:
            cmd.extend(['--storageEngine', 'wiredTiger'])
            cmd.extend(['--wiredTigerCacheSizeGB', str(self.wired_tiger_cache_size_gb)])
            if self.wired_tiger_zlib:
                cmd.extend(['--wiredTigerCollectionBlockCompressor', 'zlib'])
        if not self.journal:
            cmd.append('--nojournal')
        self._mongod_process = subprocess.Popen(cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        try:
            self.logger.info(
                'Started MongoDB (%s) pid %s port: %s dbpath: %s',
                self.mongod_cmd, self._mongod_process.pid, self.port, self.data_dir)
            self._stdout_thread = self._tail(self._mongod_process.stdout, 'stdout')
            self._stderr_thread = self._tail(self._mongod_process.stderr, 'stderr')
            wait_for_accepting_tcp_conns(port=self.port, timeout=10)
            self.mongodb_uri = 'mongodb://127.0.0.1:{port}'.format(port=self.port)
            with patch_pymongo_periodic_executor():
                self.client = pymongo.MongoClient(self.mongodb_uri)
            self.testdb = self.client.test
            # use any db you want, self.testdb is just a shortcut
        except BaseException as e:
            try:
                self._mongod_process.terminate()
                self._mongod_process.wait()
            except ProcessLookupError:
                pass
            raise e

    def stop(self):
        if self.client:
            self.client.close()
            self.client = None
            self.testdb = None
        if self._mongod_process:
            if self._mongod_process.poll() is None:
                self.logger.debug('Terminating MongoDB pid %s', self._mongod_process.pid)
                try:
                    self._mongod_process.terminate()
                    self._mongod_process.wait()
                except ProcessLookupError:
                    # already stopped
                    pass
                self.logger.info('MongoDB pid %s successfully terminated', self._mongod_process.pid)
            else:
                self.logger.warning('MongoDB pid %s has already exited', self._mongod_process.pid)
            self._mongod_process = None
        if self._stdout_thread:
            self._stdout_thread.join()
            self._stdout_thread = None
        if self._stderr_thread:
            self._stderr_thread.join()
            self._stderr_thread = None

    def _tail(self, stream, name):
        pid = self._mongod_process.pid
        def f():
            while True:
                line = stream.readline()
                if not line:
                    break
                self.logger.debug('mongod[%s]: %s', pid, line.strip())
        t = threading.Thread(target=f)
        t.start()
        return t

    def drop_everything(self):
        '''
        Drop all collections in all databases (except the system ones)
        '''
        for dbname in self.client.database_names():
            if dbname == 'local':
                continue
            for collname in self.client[dbname].collection_names():
                if collname.startswith('system.'):
                    continue
                self.logger.info('drop_everything: dropping collection %s.%s', dbname, collname)
                self.client[dbname][collname].drop()

@contextmanager
def patch_pymongo_periodic_executor():
    '''
    Enables faster pymongo.MongoClient shutdown
    '''
    pex = pymongo.periodic_executor.PeriodicExecutor
    original_run = pex._run
    def patched_run(self):
        self._interval = 0.05
        self._min_interval = 0.05
        return original_run(self)
    pex._run = patched_run
    try:
        yield
    finally:
        pex._run = original_run
