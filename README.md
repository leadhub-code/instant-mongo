
instant-mongo
=============


Installation
------------

Install current version:

```sh
$ pip install git+https://github.com/messa/instant-mongo
```

Install specific version:

```sh
$ pip install git+https://github.com/messa/instant-mongo.git@v0.1.0
```

Or add this line to your `requirements.txt`:

```
git+https://github.com/messa/instant-mongo#egg=instant-mongo
```


Usage
-----

```python
from instant_mongo import InstantMongoDB
with InstantMongoDB(data_dir=tmpdir / 'data') as im:
    im.testdb.testcoll.insert({'foo': 'bar'})
    doc, = im.testdb.testcoll.find()
    assert doc['foo'] == 'bar'
```

Available attributes and methods:

- `im.mongodb_uri` is `'mongodb://127.0.0.1:{port}'`
- `im.client` is `pymongo.MongoClient(im.mongodb_uri)`
- `im.testdb` is `im.client.testdb`
- `im.drop_everything()` drops all collections; intended for tests

If you run MongoDB in `/tmp` and you have your `/tmp` on ramdisk (tmpfs) then it's super fast. I'm recommending this setup for your tests.

WiredTiger engine is used by default which has smaller disk space footprint so there is no need for multi-GB available space (on your tmpfs `/tmp` for example).


### pytest fixture

If you are using [pytest](http://pytest.org/) to run your test and would like to have nice fixture that provides MongoDB test instance:

```python
# conftest.py

from pytest import fixture, yield_fixture
from instant_mongo import InstantMongoDB

@fixture
def mongodb(global_mongodb):
    global_mongodb.drop_everything()
    return global_mongodb.testdb

@yield_fixture(scope='session')
def global_mongodb(tmpdir_factory):
    with InstantMongoDB(data_dir=tmpdir_factory.mktemp('instant-mongo-data'), journal=False) as im:
        yield im

# test_smoke.py

def test_mongodb_works(mongodb):
    mongodb.testcoll.insert({'foo': 'bar'})
    doc, = mongodb.testcoll.find()
    assert doc['foo'] == 'bar'
```
