'''
Fork-safe pytest fixture example — mirrors the code in README.md
'''

from bson import ObjectId
from os import environ
from pymongo import MongoClient
from pytest import fixture
from threading import active_count
from instant_mongo import InstantMongoDB
from instant_mongo.util import join_pymongo_threads


@fixture(scope='session')
def mongo_uri(tmpdir_factory):
    if environ.get('TEST_MONGO_PORT'):
        yield f'mongodb://127.0.0.1:{int(environ["TEST_MONGO_PORT"])}'
    else:
        temp_dir = tmpdir_factory.mktemp('instant-mongo')
        with InstantMongoDB(data_parent_dir=temp_dir, follow_logs=False) as im:
            yield im.mongo_uri


@fixture
def db(mongo_uri):
    with MongoClient(mongo_uri) as client:
        db_name = f'test_{ObjectId()}'
        yield client[db_name]
        client.drop_database(db_name)
    join_pymongo_threads()


def test_00_no_threads_are_running():
    assert active_count() == 1


def test_01_insert_and_find(db):
    assert active_count() > 1
    db['testcoll'].insert_one({'foo': 'bar'})
    doc, = db['testcoll'].find()
    assert doc['foo'] == 'bar'


def test_02_no_leftover_threads_are_running():
    assert active_count() == 1
