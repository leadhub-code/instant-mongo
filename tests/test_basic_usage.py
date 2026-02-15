from logging import getLogger
from os import environ
from pymongo import version as pymongo_version
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import NotPrimaryError, OperationFailure
from pytest import fixture, skip, raises
from subprocess import check_call
from threading import active_count

from instant_mongo import InstantMongoDB
from instant_mongo.util import count_documents, join_pymongo_threads


logger = getLogger(__name__)


@fixture(scope='session')
def needs_mongod():
    try:
        check_call(['mongod', '--version'])
    except FileNotFoundError:
        if environ.get('CI'):
            raise Exception('mongod not found - need to be installed in a CI environment')
        else:
            skip('mongod not found')


def test_instant_mongo_db_attribute(needs_mongod, tmp_path):
    with InstantMongoDB(tmp_path) as im:
        assert isinstance(im.db, Database)
        im.db['testcoll'].insert_one({'foo': 'bar'})
        doc, = im.db['testcoll'].find()
        assert doc['foo'] == 'bar'
        assert 'testcoll' in im.db.list_collection_names()


def test_instant_mongo_client_attribute(needs_mongod, tmp_path):
    with InstantMongoDB(tmp_path) as im:
        assert isinstance(im.client, MongoClient)
        im.db['testcoll'].insert_one({'foo': 'bar'})
        doc, = im.client['test']['testcoll'].find()
        assert doc['foo'] == 'bar'


def test_instant_mongo_get_client_method(needs_mongod, tmp_path):
    with InstantMongoDB(tmp_path) as im:
        client = im.get_client()
        assert isinstance(client, MongoClient)
        assert im._client is None  # do not cache clients created by explicit calls of im.get_client()
        client['test']['testcoll'].insert_one({'foo': 'bar'})
        with client:  # MongoClient should support context manager
            doc, = client['test']['testcoll'].find()
            assert doc['foo'] == 'bar'


def test_instant_mongo_mongo_uri_attribute(needs_mongod, tmp_path):
    with InstantMongoDB(tmp_path) as im:
        assert isinstance(im.mongo_uri, str)
        im.db['testcoll'].insert_one({'foo': 'bar'})
        client = MongoClient(im.mongo_uri)
        doc, = client['test']['testcoll'].find()
        assert doc['foo'] == 'bar'


def test_instant_mongo_drop_everything_method(needs_mongod, tmp_path):
    with InstantMongoDB(tmp_path) as im:
        result = im.drop_everything()
        assert result is None  # drop_everything() doesn't return anything


def test_instant_mongo_drop_everything_method_will_delete_everything(needs_mongod, tmp_path):
    with InstantMongoDB(tmp_path) as im:
        im.db['testcoll'].insert_one({'foo': 'bar'})
        assert count_documents(im.db['testcoll']) == 1
        assert 'testcoll' in im.db.list_collection_names()
        im.drop_everything()
        assert count_documents(im.db['testcoll']) == 0
        assert 'testcoll' not in im.db.list_collection_names()


def test_instant_mongo_get_new_test_db_method(needs_mongod, tmp_path):
    with InstantMongoDB(tmp_path) as im:
        db = im.get_new_test_db()
        assert isinstance(db, Database)
        assert isinstance(db.name, str)
        assert db.client is im.client
        # check that the database name is unique
        db2 = im.get_new_test_db()
        assert db.name != db2.name


def test_as_replica_set(needs_mongod, tmp_path):
    with raises(OperationFailure):
        with InstantMongoDB(tmp_path) as im:
            im.client['admin'].command('replSetGetStatus')

    with InstantMongoDB(tmp_path, as_replica_set=True) as im:
        status = im.client['admin'].command('replSetGetStatus')
        assert status['myState'] == 1


def test_transactions(needs_mongod, tmp_path):
    try:
        with InstantMongoDB(tmp_path, as_replica_set=True) as im:
            with im.client.start_session() as session:
                with session.start_transaction():
                    im.db['test'].insert_one({'test': 1}, session=session)
                    im.db['test'].insert_one({'test': 1}, session=session)

            assert im.db['test'].count_documents({}) == 2
    except NotPrimaryError as e:
        if pymongo_version.startswith('3.'):
            skip('Fails with NotPrimaryError on pymongo 3.*')
        else:
            raise e


def test_no_leftover_threads_are_running_after_instant_mongo_is_closed(needs_mongod, tmp_path):
    assert active_count() == 1
    with InstantMongoDB(tmp_path) as im:
        im.db['testcoll'].insert_one({'foo': 'bar'})
        assert active_count() > 1  # e.g. MongoClient maintains thread(s) for replica set monitoring
    # After
    join_pymongo_threads()
    assert active_count() == 1


def test_no_threads_are_started(needs_mongod, tmp_path):
    assert active_count() == 1
    with InstantMongoDB(tmp_path) as im:
        assert active_count() == 1
        with im.get_client() as client:
            client['testdb']['testcoll'].insert_one({'foo': 'bar'})
            assert active_count() > 1  # e.g. MongoClient maintains thread(s) for replica set monitoring
        join_pymongo_threads()
        assert active_count() == 1
    # After
    assert active_count() == 1
