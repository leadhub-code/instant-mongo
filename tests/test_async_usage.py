from os import environ
from subprocess import check_call

from bson import ObjectId
from pytest import fixture, mark, skip
from pytest_asyncio import fixture as async_fixture

try:
    from pymongo import AsyncMongoClient  # noqa: F401
except ImportError:
    skip('AsyncMongoClient is not available', allow_module_level=True)

from instant_mongo import InstantMongoDB


@fixture(scope='module')
def needs_mongod():
    try:
        check_call(['mongod', '--version'])
    except FileNotFoundError:
        if environ.get('CI'):
            raise Exception('mongod not found - need to be installed in a CI environment')
        else:
            skip('mongod not found')


@fixture(scope='module')
def instant_mongo(needs_mongod, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp('instant-mongo-async')
    with InstantMongoDB(data_parent_dir=tmp_path) as im:
        yield im


@async_fixture
async def db(instant_mongo):
    async with instant_mongo.get_async_client() as client:
        db_name = f'test_{ObjectId()}'
        yield client[db_name]
        await client.drop_database(db_name)


@mark.asyncio
async def test_insert_and_find(db):
    await db['testcoll'].insert_one({'foo': 'bar'})
    doc = await db['testcoll'].find_one()
    assert doc['foo'] == 'bar'


@mark.asyncio
async def test_insert_many_and_count(db):
    await db['testcoll'].insert_many([
        {'n': 1},
        {'n': 2},
        {'n': 3},
    ])
    count = await db['testcoll'].count_documents({})
    assert count == 3


@mark.asyncio
async def test_find_with_filter(db):
    await db['testcoll'].insert_many([
        {'color': 'red', 'value': 1},
        {'color': 'blue', 'value': 2},
        {'color': 'red', 'value': 3},
    ])
    docs = await db['testcoll'].find({'color': 'red'}).to_list()
    assert len(docs) == 2
    assert all(d['color'] == 'red' for d in docs)


@mark.asyncio
async def test_update_one(db):
    await db['testcoll'].insert_one({'name': 'alice', 'score': 10})
    await db['testcoll'].update_one({'name': 'alice'}, {'$set': {'score': 20}})
    doc = await db['testcoll'].find_one({'name': 'alice'})
    assert doc['score'] == 20


@mark.asyncio
async def test_delete_one(db):
    await db['testcoll'].insert_one({'name': 'bob'})
    assert await db['testcoll'].count_documents({}) == 1
    await db['testcoll'].delete_one({'name': 'bob'})
    assert await db['testcoll'].count_documents({}) == 0


@mark.asyncio
async def test_list_collection_names(db):
    await db['coll_a'].insert_one({'x': 1})
    await db['coll_b'].insert_one({'x': 2})
    names = await db.list_collection_names()
    assert 'coll_a' in names
    assert 'coll_b' in names


@mark.asyncio
async def test_each_test_gets_isolated_db(db):
    """Each test should get a fresh database (no leftover data from other tests)."""
    count = await db['testcoll'].count_documents({})
    assert count == 0
