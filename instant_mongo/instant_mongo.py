from contextlib import ExitStack
from logging import getLogger
from os import getpid
from pathlib import Path
from pymongo import MongoClient
from pymongo.database import Database
from re import match
from shutil import rmtree
from subprocess import Popen
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import sleep, time_ns
from typing import Optional

try:
    from pymongo import AsyncMongoClient
except ImportError:
    AsyncMongoClient = None

from .port_guard import PortGuard
from .util import patch_pymongo_periodic_executor, drop_all_dbs
from .util import tcp_conns_accepted_on_port, to_path


logger = getLogger('instant_mongo')


class InstantMongoDB:
    '''
    Usage:

    with InstantMongoDB(data_dir='/tmp/data') as im:
        print(im.db.list_collection_names())

    The database is automatically stopped at the end of the with-block.

    Available attributes and methods:

    - im.mongo_uri is 'mongodb://127.0.0.1:{port}'
    - im.client is pymongo.MongoClient(im.mongodb_uri)
    - im.db is im.client['test']
    - im.drop_everything() drops all databases and collections; intended for tests
    '''

    wait_timeout = 10

    def __init__(self, data_parent_dir=None, *, data_dir=None, port=None, as_replica_set=False, delete_data_dir_on_exit=None, follow_logs=False):
        self.logger = logger
        self.port: Optional[int] = port
        self.as_replica_set = as_replica_set
        self.delete_data_dir_on_exit = delete_data_dir_on_exit
        self.follow_logs = follow_logs
        self._exit_stack = None
        # figure out self.data_dir
        if data_dir:
            self.data_dir = to_path(data_dir)
        elif data_parent_dir:
            self.data_dir = to_path(data_parent_dir) / self._generate_data_dir_name()
            if self.delete_data_dir_on_exit is None:
                self.delete_data_dir_on_exit = True
        else:
            self.data_dir = None  # will be created later

        self._mongodb_process = None
        self._client: Optional[MongoClient] = None

    @property
    def mongo_uri(self) -> str:
        if self._mongodb_process is None:
            raise RuntimeError('MongoDB process is not running')
        return f'mongodb://127.0.0.1:{self.port}'

    def _generate_data_dir_name(self):
        return f'instant-mongo-data.{getpid()}.{time_ns()}'

    def _prepare_data_dir(self):
        if self.data_dir is None:
            temp_dir = self._exit_stack.enter_context(TemporaryDirectory(prefix=f'instant-mongo.{getpid()}.'))
            self.data_dir = Path(temp_dir) / self._generate_data_dir_name()
        assert isinstance(self.data_dir, Path)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        assert self._exit_stack is None
        self._exit_stack = ExitStack()
        try:
            self._prepare_data_dir()
            if not self.port:
                port_guard = self._exit_stack.enter_context(PortGuard())
                self.port = port_guard.get_available_port()
            self._mongodb_process = MongoDBProcess(
                logger=self.logger,
                data_dir=self.data_dir,
                port=self.port,
                as_replica_set=self.as_replica_set,
                follow_logs=self.follow_logs)
            self._exit_stack.callback(self._mongodb_process.stop)
            self._mongodb_process.start()
            self._wait_for_accepting_tcp_conns()
            self._client = None
            self._init_rs()
        except BaseException:
            self._exit_stack.close()
            self._exit_stack = None
            self._mongodb_process = None
            raise

    def _wait_for_accepting_tcp_conns(self):
        while True:
            if not self._mongodb_process.is_alive():
                raise Exception('MongoDB process exited before it started to accept connections')
            if tcp_conns_accepted_on_port(self.port):
                return
            sleep(.01)

    def _init_rs(self):
        if not self.as_replica_set:
            return
        # Initialize the replica set. We need directConnection=True to connect as a standalone client.
        with self.get_client(directConnection=True) as client:
            client.admin.command('replSetInitiate')
            # Wait for the primary to be elected.
            while True:
                status = client.admin.command('replSetGetStatus')
                if status['myState'] == 1:
                    break
                sleep(.01)

    def stop(self):
        if self._client is not None:
            logger.debug('Calling self._client.close() pid=%d', getpid())
            self._client.close()
            logger.debug('Done self._client.close()')
            self._client = None
        if self._exit_stack is not None:
            self._exit_stack.close()
            self._exit_stack = None
        self._mongodb_process = None
        if self.delete_data_dir_on_exit and self.data_dir is not None:
            # Pytest doesn't delete tmp dirs immediately. So after a few runs
            # a smaller /tmp filesystem could be easily filled up.
            # So we delete the data dir explicitly.
            rmtree(self.data_dir, ignore_errors=True)
            self.data_dir = None

    @property
    def client(self) -> MongoClient:
        '''
        Returns a pymongo.MongoClient instance connected to the MongoDB server.

        The instance will also be cached and returned again on subsequent calls.
        '''
        if not self._client:
            self._client = self.get_client(connect=True)
        return self._client

    def close_client(self):
        '''
        Closes the cached pymongo.MongoClient instance (if any).

        The instance will be recreated on next access to `im.client`.

        This method is intended to be used when you need to close the client
        after each test to make sure you have no leftover threads running
        (e.g. for fork safety).
        '''
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_client(self, **kwargs) -> MongoClient:
        '''
        Returns a pymongo.MongoClient instance connected to the MongoDB server.

        The instance will not be cached and will be created anew on each call.
        '''
        # TODO: remove patch_pymongo_periodic_executor - it was used only for old pymongo versions
        with patch_pymongo_periodic_executor():
            return MongoClient(self.mongo_uri, **kwargs)

    def get_async_client(self, **kwargs) -> AsyncMongoClient:
        '''
        Returns a pymongo.AsyncMongoClient instance connected to the MongoDB server.

        The instance will not be cached and will be created anew on each call.
        Can be used as an async context manager.
        '''
        if AsyncMongoClient is None:
            raise RuntimeError('AsyncMongoClient is not available - pymongo 4.x is required')
        return AsyncMongoClient(self.mongo_uri, **kwargs)

    @property
    def db(self) -> Database:
        '''
        Returns a pymongo.Database instance connected to the MongoDB server working on the 'test' database.

        The Database instance comes from the cached MongoClient instance.
        '''
        return self.client['test']

    def get_new_test_db(self) -> Database:
        '''
        Returns a pymongo.Database instance connected to the MongoDB server.
        Database name will be randomly generated.
        '''
        # If you have many tests and you create a new database for each test, don't forget
        # to drop them after the test - MongoDB might run out of space or open file handles.
        # You can use the drop_everything() method.
        return self.client[f'test_{time_ns()}']

    @property
    def mongodb_uri(self) -> str:
        '''
        For backwards compatibility. Please use `mongo_uri` attribute instead.
        '''
        return self.mongo_uri

    def drop_everything(self):
        '''
        Drops all databases and collections.

        Intended to clean up the database after each test.
        '''
        with ExitStack() as stack:
            client = self._client or stack.enter_context(self.get_client(connect=True))
            drop_all_dbs(client)


class MongoDBProcess:

    def __init__(self, logger, data_dir, port, as_replica_set, follow_logs):
        self._logger = logger
        self._data_dir = data_dir.resolve()
        self._stdout_path = data_dir / 'mongod-stdout.log'
        self._stderr_path = data_dir / 'mongod-stderr.log'
        self._port = port
        self._mongod_process = None
        self._stdout_reader = None
        self._stderr_reader = None
        self._as_replica_set = as_replica_set
        self._follow_logs = follow_logs

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
            ]
            if self._as_replica_set:
                cmd.extend([
                    '--replSet', 'test-rs',
                    '--oplogSize', '1000',
                ])
            with self._stdout_path.open('wb') as stdout_file, self._stderr_path.open('wb') as stderr_file:
                self._mongod_process = Popen(
                    cmd,
                    stdout=stdout_file,
                    stderr=stderr_file)
            if self._follow_logs:
                self._stdout_reader = OutputFileReader(
                    self._logger,
                    self._stdout_path,
                    f'mongod[{self._mongod_process.pid}] out')
                self._stderr_reader = OutputFileReader(
                    self._logger,
                    self._stderr_path,
                    f'mongod[{self._mongod_process.pid}] err')
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
            self._stdout_reader.stop()
            self._stdout_reader = None
        if self._stderr_reader:
            self._stderr_reader.stop()
            self._stderr_reader = None

    def is_alive(self):
        return self._mongod_process.poll() is None


class OutputFileReader:

    def __init__(self, logger, file_path, name):
        self.logger = logger
        self.file_path = file_path
        self.name = name
        self.stop_event = Event()
        self.thread = Thread(target=self._run)
        self.thread.start()

    def _run(self):
        with self.file_path.open('rb') as f:
            while not self.stop_event.is_set():
                line = f.readline()
                if not line:
                    sleep(0.01)
                    continue
                try:
                    line = line.decode()
                except Exception:
                    line = str(line)
                try:
                    line = self._preprocess_line(line)
                except Exception as e:
                    self.logger.exception('Failed to preprocess line %r: %r', line, e)
                self.logger.debug('%s: %s', self.name, line.rstrip())

    def stop(self):
        self.stop_event.set()
        self.thread.join()
        self.thread = None

    def _preprocess_line(self, line):
        m = match(
            r'^[0-9]{4}-[0-9]{2}-[0-9]{2}'
            r'T[0-9]{2}:[0-9]{2}:[0-9]{2}'
            r'\.[0-9]{3}[+-][0-9]{4} (.*)', line)
        if m:
            return m.group(1)
        return line
