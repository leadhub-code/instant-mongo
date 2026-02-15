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
$ pip install https://github.com/leadhub-code/instant-mongo/archive/v1.0.6.zip
# or
$ pip install git+https://github.com/leadhub-code/instant-mongo.git@v1.0.6
```

Or add this line to your `requirements.txt`:

```
instant-mongo @ https://github.com/leadhub-code/instant-mongo/archive/v1.0.6.zip
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
- `im.get_client()` returns a new `pymongo.MongoClient(im.mongo_uri)` (you can customize `MongoClient` kwargs)
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
        # use already running MongoDB instance
        yield MongoClient(port=int(environ['TEST_MONGO_PORT']))
    else:
        # run temporary MongoDB instance using instant-mongo
        temp_dir = tmpdir_factory.mktemp('instant-mongo')
        with InstantMongoDB(data_parent_dir=temp_dir) as im:
            yield im.client

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
def async_mongo_client(tmpdir_factory):
    if environ.get('TEST_MONGO_PORT'):
        yield AsyncMongoClient(port=int(environ['TEST_MONGO_PORT']))
    else:
        temp_dir = tmpdir_factory.mktemp('instant-mongo')
        with InstantMongoDB(data_parent_dir=temp_dir) as im:
            yield im.get_async_client()

@pytest_asyncio.fixture
async def async_db(async_mongo_client):
    db_name = f'test_{ObjectId()}'
    yield async_mongo_client[db_name]
    await async_mongo_client.drop_database(db_name)

# test_smoke.py

import pytest

@pytest.mark.asyncio
async def test_mongodb_works(async_db):
    await async_db['testcoll'].insert_one({'foo': 'bar'})
    doc = await async_db['testcoll'].find_one()
    assert doc['foo'] == 'bar'
```


### Fork-safe pytest fixture

When you need to be sure no leftover threads are running from MongoClient or InstantMongoDB when a test finishes.

```python
# conftest.py

from bson import ObjectId
from os import environ
from pymongo import MongoClient
from pytest import fixture
from instant_mongo import InstantMongoDB

@fixture(scope='session')
def mongo_client_factory(tmpdir_factory):
    if environ.get('TEST_MONGO_PORT'):
        # use already running MongoDB instance
        yield lambda: MongoClient(port=int(environ['TEST_MONGO_PORT']))
    else:
        # run temporary MongoDB instance using instant-mongo
        temp_dir = tmpdir_factory.mktemp('instant-mongo')
        with InstantMongoDB(data_parent_dir=temp_dir) as im:
            yield im.get_client

@fixture
def db(mongo_client_factory):
    with mongo_client_factory() as client:
        db_name = f'test_{ObjectId()}'
        yield client[db_name]
        client.drop_database(db_name)


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
                    follow_logs=False) as im:
    ...
```

**Constructor parameters:**

- `data_parent_dir` — parent directory where a uniquely-named data subdirectory will be created. When used, `delete_data_dir_on_exit` defaults to `True`.
- `data_dir` — explicit path for the MongoDB data directory. If neither `data_dir` nor `data_parent_dir` is provided, a temporary directory is created automatically.
- `port` — TCP port for MongoDB to listen on. If not provided, an available port is selected automatically.
- `as_replica_set` — if `True`, MongoDB is started as a single-node replica set (required for transactions).
- `delete_data_dir_on_exit` — if `True` (or `None` and no `data_dir` is provided), the data directory is deleted when the context manager exits.
- `follow_logs` — if `True`, `mongod` stdout/stderr log files are read and forwarded to Python logging.

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
