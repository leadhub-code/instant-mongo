from pathlib import Path
import py.path
from shutil import rmtree

from instant_mongo import InstantMongoDB


def test_run(tmpdir):
    dd = tmpdir / 'data'
    assert isinstance(dd, py._path.local.LocalPath), type(dd)
    for data_dir in [dd, str(dd), Path(str(dd))]:
        print()
        print('data_dir: {!r}'.format(data_dir))
        im = InstantMongoDB(data_dir=data_dir, journal=False)
        with im:
            im.db.testcoll.insert({'foo': 'bar'})
            doc, = im.db.testcoll.find()
            assert doc['foo'] == 'bar'
            im.db.testcoll.drop()


def test_drop_everything(tmpdir):
    im = InstantMongoDB(data_dir=tmpdir / 'data', journal=False)
    with im:
        im.db.testcoll.insert({'foo': 'bar'})
        assert im.db.testcoll.count() == 1
        im.drop_everything()
        assert im.db.testcoll.count() == 0


def test_disable_journal(tmpdir):
    tmpdir = Path(str(tmpdir))
    with InstantMongoDB(data_dir=tmpdir / 'data1', journal=True):
        assert (tmpdir / 'data1/journal').is_dir()
    with InstantMongoDB(data_dir=tmpdir / 'data2', journal=False):
        assert (tmpdir / 'data2/journal').is_dir() == False
    # cleanup
    rmtree(str(tmpdir / 'data1/journal'))


def test_testdb_backward_compatibility(tmpdir):
    im = InstantMongoDB(data_dir=tmpdir / 'data', journal=False)
    with im:
        assert im.testdb is im.db

