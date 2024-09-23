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
$ pip install https://github.com/leadhub-code/instant-mongo/archive/v1.0.5.zip
# or
$ pip install git+https://github.com/leadhub-code/instant-mongo.git@v1.0.5
```

Or add this line to your `requirements.txt`:

```
instant-mongo @ https://github.com/leadhub-code/instant-mongo/archive/v1.0.5.zip
```


Usage
-----

```python
from instant_mongo import InstantMongoDB
with InstantMongoDB() as im:
    im.db.testcoll.insert({'foo': 'bar'})
    doc, = im.db.testcoll.find()
    assert doc['foo'] == 'bar'
```

Available attributes and methods:

- `im.mongo_uri` is `'mongodb://127.0.0.1:{port}'`
- `im.client` is `pymongo.MongoClient(im.mongodb_uri)`
- `im.db` is `im.client.test`
- `im.drop_everything()` drops all collections; intended for tests

If you run MongoDB in `/tmp` and you have your `/tmp` on ramdisk (tmpfs) then it's super fast. I'm recommending this setup for your tests.


### pytest fixture

If you are using [pytest](http://pytest.org/) to run your test and would like to have nice fixture that provides MongoDB test instance:

```python
# conftest.py

from bson import ObjectId
from pytest import fixture
from instant_mongo import InstantMongoDB

@fixture(scope='session')
def mongo_client(tmpdir_factory):
    if os.environ.get('TEST_MONGO_PORT'):
        # use already running MongoDB instance
        yield MongoClient(port=int(os.environ['TEST_MONGO_PORT']))
    else:
        # run temporary MongoDB instance using instant-mongo
        temp_dir = tmpdir_factory.mktemp('instant-mongo')
        with InstantMongoDB(data_parent_dir=temp_dir) as im:
            yield im.get_client()

@fixture
def db(mongo_client):
    db_name = f'test_{ObjectId()}'
    yield mongo_client[db_name]

# test_smoke.py

def test_mongodb_works(db):
    db['testcoll'].insert({'foo': 'bar'})
    doc, = db['testcoll'].find()
    assert doc['foo'] == 'bar'
```

This is compatible with parallel test running via pytest-xdist.


Similar projects
----------------

Projects helping with testing of MongoDB-based applications:

- [github.com/fakemongo/fongo](https://github.com/fakemongo/fongo) - In-memory java implementation of MongoDB
- [github.com/AMCN41R/harness](https://github.com/AMCN41R/harness) - MongoDB Integration Test Framework, C#
