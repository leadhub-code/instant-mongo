from bson import ObjectId
from os import environ
from pymongo import MongoClient
from pytest import fixture
from instant_mongo import InstantMongoDB
from threading import active_count

from instant_mongo.util import join_pymongo_threads


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

    join_pymongo_threads()
    assert active_count() == 1


def test_00_no_threads_are_running():
    assert active_count() == 1


def test_01_insert_and_find(db):
    assert active_count() > 1
    db['testcoll'].insert_one({'foo': 'bar'})
    doc, = db['testcoll'].find()
    assert doc['foo'] == 'bar'


def test_02_no_leftover_threads_are_running():
    assert active_count() == 1
