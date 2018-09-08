instant-mongo: MongoDB runner for your tests
============================================

[![Build Status](https://travis-ci.org/leadhub-code/instant-mongo.svg?branch=master)](https://travis-ci.org/leadhub-code/instant-mongo)

Run MongoDB easily in your integration tests or other code that depends on a temporary MongoDB server.


Installation
------------

Install current version:

```sh
$ pip install git+https://github.com/leadhub-code/instant-mongo
```

Install specific version:

```sh
$ pip install https://github.com/leadhub-code/instant-mongo/archive/v1.0.2.zip
# or
$ pip install git+https://github.com/leadhub-code/instant-mongo.git@v1.0.2
```

Or add this line to your `requirements.txt`:

```
https://github.com/leadhub-code/instant-mongo/archive/v1.0.2.zip#egg=instant-mongo==1.0.2
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

from pytest import fixture, yield_fixture
from instant_mongo import InstantMongoDB

@fixture
def mongodb(global_mongodb):
    return global_mongodb.get_new_test_db()

@yield_fixture(scope='session')
def global_mongodb(tmpdir_factory):
    temp_dir = tmpdir_factory.mktemp('instant-mongo')
    with InstantMongoDB(data_parent_dir=temp_dir) as im:
        yield im

# test_smoke.py

def test_mongodb_works(mongodb):
    mongodb.testcoll.insert({'foo': 'bar'})
    doc, = mongodb.testcoll.find()
    assert doc['foo'] == 'bar'
```

This is compatible with parallel test running via pytest-xdist.


Similar projects
----------------

Projects helping with testing of MongoDB-based applications:

- [github.com/fakemongo/fongo](https://github.com/fakemongo/fongo) - In-memory java implementation of MongoDB
- [github.com/AMCN41R/harness](https://github.com/AMCN41R/harness) - MongoDB Integration Test Framework, C#

