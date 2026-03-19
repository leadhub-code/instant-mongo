instant-mongo: MongoDB runner for your tests
============================================

Run MongoDB easily in your integration tests or other code that depends on a temporary MongoDB server.


Installation
------------

Install current version:

```sh
$ pip install https://github.com/leadhub-code/instant-mongo/archive/master.zip
```

Install specific version:

```sh
$ pip install https://github.com/leadhub-code/instant-mongo/archive/v1.1.0.zip
# or
$ pip install git+https://github.com/leadhub-code/instant-mongo.git@v1.1.0
```

Or add this line to your `requirements.txt`:

```
instant-mongo @ https://github.com/leadhub-code/instant-mongo/archive/v1.1.0.zip
```


Usage
-----

You need to have `mongod` installed. See [installation instructions](https://www.mongodb.com/docs/manual/installation/).

Example:

```python
from instant_mongo import InstantMongoDB
with InstantMongoDB() as im:
    im.db['testcoll'].insert_one({'foo': 'bar'})
    doc, = im.db['testcoll'].find()
    assert doc['foo'] == 'bar'
```

Available attributes and methods:

- `im.mongo_uri` is `"mongodb://127.0.0.1:{port}"`
- `im.client` is `pymongo.MongoClient(im.mongo_uri)` (created only once and cached in `im` object)
- `im.get_client(**kwargs)` returns a new `pymongo.MongoClient(im.mongo_uri, **kwargs)`
- `im.get_async_client(**kwargs)` returns a new `pymongo.AsyncMongoClient(im.mongo_uri, **kwargs)` (pymongo 4.x+)
- `im.db` is `im.client["test"]` (`pymongo.Database`)
- `im.get_new_test_db()` returns a new `pymongo.Database` instance with a randomly generated name
- `im.drop_everything()` drops all databases and collections; intended for tests

If you run MongoDB in `/tmp` and you have your `/tmp` on ramdisk (tmpfs) then it's super fast. I'm recommending this setup for your tests.


### pytest fixture

If you are using [pytest](http://pytest.org/) to run your tests and would like to have nice fixture that provides MongoDB test instance:

```python
# conftest.py

from bson import ObjectId
from os import environ
from pymongo import MongoClient
from pytest import fixture
from instant_mongo import InstantMongoDB

@fixture(scope='session')
def mongo_client(tmpdir_factory):
    if environ.get('TEST_MONGO_PORT'):
        # Use already running MongoDB instance (e.g. in Github Actions)
        yield MongoClient(port=int(environ['TEST_MONGO_PORT']))
    else:
        # Run temporary MongoDB instance using instant-mongo
        temp_dir = tmpdir_factory.mktemp('instant-mongo')
        with InstantMongoDB(data_parent_dir=temp_dir) as im:
            yield im.get_client(tz_aware=True)

@fixture
def db(mongo_client):
    db_name = f'test_{ObjectId()}'
    yield mongo_client[db_name]
    mongo_client.drop_database(db_name)

# test_smoke.py

def test_mongodb_works(db):
    db['testcoll'].insert_one({'foo': 'bar'})
    doc, = db['testcoll'].find()
    assert doc['foo'] == 'bar'
```

This is compatible with parallel test running via pytest-xdist.


### Async pytest fixture (pymongo 4.x+)

If you are using `AsyncMongoClient` from pymongo 4.x:

```python
# conftest.py

from bson import ObjectId
from os import environ
from pymongo import AsyncMongoClient
from pytest import fixture
from instant_mongo import InstantMongoDB
import pytest_asyncio

@fixture(scope='session')
def instant_mongo_uri(tmpdir_factory):
    if environ.get('TEST_MONGO_PORT'):
        # Use already running MongoDB instance (e.g. in Github Actions)
        yield f'mongodb://127.0.0.1:{int(environ["TEST_MONGO_PORT"])}'
    else:
        temp_dir = tmpdir_factory.mktemp('instant-mongo')
        with InstantMongoDB(data_parent_dir=temp_dir) as im:
            yield im.mongo_uri

@pytest_asyncio.fixture
async def async_db(instant_mongo_uri):
    # Create new AsyncMongoClient instance for each test to prevent issues
    # with each test running with a different asyncio loop.
    async with AsyncMongoClient(instant_mongo_uri) as client:
        db_name = f'test_{ObjectId()}'
        yield client[db_name]
        await client.drop_database(db_name)

# test_smoke.py

import pytest

@pytest.mark.asyncio
async def test_mongodb_works(async_db):
    await async_db['testcoll'].insert_one({'foo': 'bar'})
    doc = await async_db['testcoll'].find_one()
    assert doc['foo'] == 'bar'
```


### Fork-safe pytest fixture

When you create a PyMongo MongoClient, it will start background threads for replica set monitoring.
It is not a good idea to fork new processes when there are threads running (unless you are using a [_forkserver_ start method](https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods)).

When you need to be sure no leftover threads are running from MongoClient or InstantMongoDB when a test finishes,
you need to make sure `follow_logs` is not enabled in `InstantMongoDB` constructor and create a new `MongoClient` instance for each test.

```python
# conftest.py

from bson import ObjectId
from os import environ
from pymongo import MongoClient
from pytest import fixture
from instant_mongo import InstantMongoDB
from instant_mongo.util import join_pymongo_threads

@fixture(scope='session')
def mongo_uri(tmpdir_factory):
    if environ.get('TEST_MONGO_PORT'):
        # Use already running MongoDB instance (e.g. in Github Actions)
        yield f'mongodb://127.0.0.1:{int(environ["TEST_MONGO_PORT"])}'
    else:
        # Run temporary MongoDB instance using instant-mongo
        temp_dir = tmpdir_factory.mktemp('instant-mongo')
        with InstantMongoDB(data_parent_dir=temp_dir, follow_logs=False) as im:
            yield im.mongo_uri

@fixture
def db(mongo_uri):
    with MongoClient(mongo_uri) as client:
        db_name = f'test_{ObjectId()}'
        yield client[db_name]
        client.drop_database(db_name)
    join_pymongo_threads()  # wait for pymongo background threads to finish


# test_smoke.py

from threading import active_count

def test_mongodb_works(db):
    db['testcoll'].insert_one({'foo': 'bar'})
    doc, = db['testcoll'].find()
    assert doc['foo'] == 'bar'
    assert active_count() > 1  # you have MongoClient threads running now


def test_something_else():
    assert active_count() == 1  # but here you have no leftover threads running from MongoClient or InstantMongoDB
```


API
---

### `InstantMongoDB`

Context manager that starts and stops a temporary MongoDB server.

```python
with InstantMongoDB(data_parent_dir=None, *, data_dir=None, port=None,
                    as_replica_set=False, delete_data_dir_on_exit=None,
                    follow_logs=False, mongod_bin='mongod') as im:
    ...
```

**Constructor parameters:**

- `data_parent_dir` — parent directory where a uniquely-named data subdirectory will be created. When used, `delete_data_dir_on_exit` defaults to `True`.
- `data_dir` — explicit path for the MongoDB data directory. If neither `data_dir` nor `data_parent_dir` is provided, a temporary directory is created automatically.
- `port` — TCP port for MongoDB to listen on. If not provided, an available port is selected automatically.
- `as_replica_set` — if `True`, MongoDB is started as a single-node replica set (required for transactions).
- `delete_data_dir_on_exit` — if `True` (or `None` and no `data_dir` is provided), the data directory is deleted when the context manager exits.
- `follow_logs` — if `True`, `mongod` stdout/stderr will be read (in background threads) and forwarded to Python logging.
- `mongod_bin` — path or name of the `mongod` binary (default: `'mongod'`).

**Properties:**

- `im.mongo_uri` → `str` — MongoDB connection string, e.g. `"mongodb://127.0.0.1:19042"`
- `im.client` → `pymongo.MongoClient` — cached client instance (created on first access)
- `im.db` → `pymongo.database.Database` — shortcut for `im.client["test"]`

**Methods:**

- `im.get_client(**kwargs)` → `pymongo.MongoClient` — creates a new (uncached) client. Accepts the same keyword arguments as `pymongo.MongoClient`. The returned client can be used as a context manager.
- `im.get_async_client(**kwargs)` → `pymongo.AsyncMongoClient` — creates a new async client (pymongo 4.x+). Accepts the same keyword arguments as `pymongo.AsyncMongoClient`. The returned client can be used as an async context manager.
- `im.get_new_test_db()` → `pymongo.database.Database` — returns a database with a randomly generated name, useful for test isolation.
- `im.close_client()` — closes the cached client (if any). The client will be recreated on next access to `im.client`.
- `im.drop_everything()` — drops all databases and collections (except internal ones). Intended for cleanup between tests.
- `im.start()` / `im.stop()` — start and stop the MongoDB process manually (normally handled by the context manager).


Similar projects
----------------

Projects helping with testing of MongoDB-based applications:

- [github.com/fakemongo/fongo](https://github.com/fakemongo/fongo) - In-memory java implementation of MongoDB
- [github.com/AMCN41R/harness](https://github.com/AMCN41R/harness) - MongoDB Integration Test Framework, C#


Changelog
---------

### Development version

### 1.1.0 (2026-03-19)

- Fix `drop_all_dbs` to drop entire databases instead of just collections
- Add `mongod_bin` parameter to allow overriding the `mongod` binary path
- Switch build backend from setuptools to hatchling
- Replace `patch_pymongo_periodic_executor` with simpler `pymongo.common.MIN_HEARTBEAT_INTERVAL` patch (0.5s → 0.02s) for faster MongoClient shutdown across all pymongo versions
- Add `DeprecationWarning` to `mongodb_uri` property (use `mongo_uri` instead)
- Fix `PortGuard` port overflow by adding wraparound at 65535
- Add tests for `follow_logs=True`, `drop_all_collections`, error handling on start failure
- Switch to uv for dependency management and builds

### 1.0.7 (2026-02-15)

- Add `get_async_client()` method and async pytest fixture example
- Add `close_client()` method
- Refactor `InstantMongoDB` — add `delete_data_dir_on_exit` and `follow_logs` parameters
- Replace stdout/stderr pipe threads with file-based output
- Improve `stop()` — more robust `rmtree` cleanup
- Improve fork safety

**Breaking changes:**

- `data_dir`, `port` and `as_replica_set` are now keyword-only parameters
- `mongo_uri` is now a property — raises `RuntimeError` if accessed before `start()`
- When using `data_parent_dir`, the data directory is now automatically deleted on exit (if `delete_data_dir_on_exit` not explicitly set to `False`)

### 1.0.6 (2025-07-15)

- Add `as_replica_set` flag — start MongoDB as a single-node replica set (required for transactions)
- Add `connect=True` when creating `im.client`

### 1.0.5 (2024-09-23)

- Add `pyproject.toml`, remove `setup.py`
- Remove `--nojournal` option that was removed in MongoDB 7.0 & add MongoDB 7.0 to CI version matrix
- Hotfix `PeriodicExecutor` `AttributeError` for pymongo 4.9.1
  - There was a monkey patch for `PeriodicExecutor` to make closing MongoClient faster, but it stopped working for pymongo 4.9+.

### 1.0.4 (2023-06-12)

- Fix `patch_pymongo_periodic_executor`
- Add linter, fix linter warnings

### 1.0.3 (2022-09-21)

- Add method `get_client()` that can pass params to `MongoClient`

### 1.0.2 (2018-09-08)

- Migrate to pymongo 3.6/3.7 `list_database_names`/`list_collection_names` and `count_documents`

### 1.0.1 (2017-05-30)

- Fix warnings: explicitly close subprocess stdout/stderr stream
- Add custom port support (PR #7)

### 1.0.0 (2017-03-09)
