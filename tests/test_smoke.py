import os
import pymongo
from pytest import skip
import subprocess

from instant_mongo import InstantMongoDB
from instant_mongo.util import count_documents


def skip_if_no_mongod():
    try:
        subprocess.check_call(['mongod', '--version'])
    except FileNotFoundError:
        if os.environ.get('CI'):
            raise Exception('mongod not found - need to be installed in a CI environment')
        else:
            skip('mongod not found')


def test_example(tmpdir):
    skip_if_no_mongod()
    with InstantMongoDB(tmpdir) as im:
        im.db.testcoll.insert_one({'foo': 'bar'})
        doc, = im.db.testcoll.find()
        assert doc['foo'] == 'bar'
        assert 'testcoll' in im.db.list_collection_names()

        doc, = im.client.test.testcoll.find()
        assert doc['foo'] == 'bar'

        client = pymongo.MongoClient(im.mongo_uri)
        doc, = client.test.testcoll.find()
        assert doc['foo'] == 'bar'


def test_get_new_test_db(tmpdir):
    skip_if_no_mongod()
    with InstantMongoDB(tmpdir) as im:
        db1 = im.get_new_test_db()
        db2 = im.get_new_test_db()
        assert db1.name != db2.name


def test_drop_everything(tmpdir):
    skip_if_no_mongod()
    with InstantMongoDB(tmpdir) as im:
        im.db['testcoll'].insert_one({'foo': 'bar'})
        assert 'testcoll' in im.db.list_collection_names()
        assert count_documents(im.db['testcoll']) == 1
        im.drop_everything()
        assert 'testcoll' not in im.db.list_collection_names()
        assert count_documents(im.db['testcoll']) == 0
