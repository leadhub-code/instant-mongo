import logging
from os import getpid
from pathlib import Path
import re
import subprocess
import threading
from time import monotonic, time, sleep

from .port_guard import PortGuard
from .util import patch_pymongo_periodic_executor, drop_all_dbs
from .util import tcp_conns_accepted_on_port, to_path


logger = logging.getLogger('instant_mongo')


class InstantMongoDB:
    '''
    Usage:

    with InstantMongoDB(data_dir='/tmp/data') as im:
        print(im.db.collection_names())

    The database is automatically stopped at the end of the with-block.

    Available attributes and methods:

    - im.mongodb_uri is 'mongodb://127.0.0.1:{port}'
    - im.client is pymongo.MongoClient(im.mongodb_uri)
    - im.db is im.client.test
    - im.drop_everything() drops all collections; intended for tests
    '''

    wait_timeout = 10

    def __init__(self, data_parent_dir=None, data_dir=None):
        self.logger = logger
        self.port = None
        self.mongo_uri = None
        self._port_guard = None
        self._temp_dir = None
        self._mongodb_process = None

        # figure out self.data_dir
        if data_dir:
            self.data_dir = to_path(data_dir)
        else:
            if not data_parent_dir:
                from tempfile import TemporaryDirectory
                self._temp_dir = TemporaryDirectory('.instant-mongo')
                data_parent_dir = self._temp_dir
            self.data_dir = to_path(data_parent_dir) / \
                self._generate_data_dir_name()

    def _generate_data_dir_name(self):
        return 'instant-mongo-data.{pid}-{ms}'.format(
            pid=getpid(), ms=int(time() * 10**6))

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        try:
            if not self.port:
                self._port_guard = PortGuard()
                self.port = self._port_guard.get_available_port()
            self.data_dir.mkdir(parents=True)
            self._mongodb_process = MongoDBProcess(
                logger=self.logger,
                data_dir=self.data_dir,
                port=self.port)
            self._mongodb_process.start()
            self._wait_for_accepting_tcp_conns()
            self._client = None
            self.mongo_uri = 'mongodb://127.0.0.1:{}'.format(self.port)
        except BaseException as e:
            self.stop()
            raise e

    def _wait_for_accepting_tcp_conns(self):
        t0 = monotonic()
        while True:
            if not self._mongodb_process.is_alive():
                raise Exception('MongoDB process exited before it started to accept connections')
            if tcp_conns_accepted_on_port(self.port):
                return
            sleep(.01)

    def stop(self):
        if self._mongodb_process:
            self._mongodb_process.stop()
            self._mongodb_process = None
        if self._port_guard:
            self._port_guard.close()
            self._port_guard = None
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None

    @property
    def client(self):
        if not self._client:
            self._client = self._create_client()
        return self._client

    def _create_client(self):
        import pymongo
        with patch_pymongo_periodic_executor():
            return pymongo.MongoClient(self.mongo_uri)

    @property
    def db(self):
        return self.client['test']

    def get_new_test_db(self):
        name = 'test_{}'.format(int(time() * 10**6))
        return self.client[name]

    @property
    def mongodb_uri(self):
        '''
        For backwards compatibility
        '''
        return self.mongo_uri

    def drop_everything(self):
        drop_all_dbs(self.client)


class MongoDBProcess:

    def __init__(self, logger, data_dir, port):
        self._logger = logger
        self._data_dir = data_dir.resolve()
        self._port = port
        self._mongod_process = None
        self._stdout_reader = None
        self._stderr_reader = None

    def start(self):
        try:
            assert self._mongod_process is None
            cmd = [
                'mongod',
                '--dbpath', str(self._data_dir),
                '--port', str(self._port),
                '--bind_ip', '127.0.0.1',
                '--directoryperdb',
                '--storageEngine', 'wiredTiger',
                '--wiredTigerCacheSizeGB', '1',
                '--nojournal',
            ]
            self._mongod_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            self._stdout_reader = OutputReader(
                self._logger,
                self._mongod_process.stdout,
                'mongod[{}] out'.format(self._mongod_process.pid))
            self._stderr_reader = OutputReader(
                self._logger,
                self._mongod_process.stderr,
                'mongod[{}] err'.format(self._mongod_process.pid))
        except BaseException as e:
            self.stop()
            raise e

    def stop(self):
        if self._mongod_process:
            self._logger.debug('Shutting down mongod[%s]', self._mongod_process.pid)
            self._mongod_process.terminate()
            self._mongod_process.wait()
            self._mongod_process = None
        if self._stdout_reader:
            self._stdout_reader.wait()
            self._stdout_reader = None
        if self._stderr_reader:
            self._stderr_reader.wait()
            self._stderr_reader = None

    def is_alive(self):
        return self._mongod_process.poll() is None


class OutputReader:

    def __init__(self, logger, stream, name):
        self.logger = logger
        self.stream = stream
        self.name = name
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def run(self):
        while True:
            line = self.stream.readline()
            if not line:
                self.logger.debug('%s closed', self.name)
                break
            try:
                line = line.decode()
            except Exception as e:
                line = str(line)
            try:
                line = self._preprocess_line(line)
            except Exception as e:
                self.logger.exception('Failed to preprocess line %r: %r', line, e)
            self.logger.debug('%s: %s', self.name, line.rstrip())

    def wait(self):
        self.thread.join()
        self.thread = None

    def _preprocess_line(self, line):
        m = re.match(
            r'^[0-9]{4}-[0-9]{2}-[0-9]{2}'
            r'T[0-9]{2}:[0-9]{2}:[0-9]{2}'
            r'\.[0-9]{3}[+-][0-9]{4} (.*)', line)
        if m:
            return m.group(1)
        return line
