from contextlib import contextmanager
from pathlib import Path
import pymongo


def to_path(p):
    try:
        return Path(p)
    except Exception:
        return Path(str(p))


def list_database_names(client):
    if pymongo.version_tuple >= (3, 6):
        return client.list_database_names()
    else:
        return client.database_names()


def list_collection_names(db):
    if pymongo.version_tuple >= (3, 6):
        return db.list_collection_names()
    else:
        return db.collection_names()


def count_documents(collection, filter=None, **kwargs):
    if pymongo.version_tuple >= (3, 7):
        return collection.count_documents(filter or {}, **kwargs)
    else:
        return collection.count(filter, **kwargs)


def drop_all_dbs(client):
    for db_name in sorted(list_database_names(client)):
        if db_name == 'local':
            continue
        drop_all_collections(client[db_name])


def drop_all_collections(db):
    for c_name in sorted(list_collection_names(db)):
        if c_name.startswith('system.'):
            continue
        db[c_name].drop()


@contextmanager
def patch_pymongo_periodic_executor():
    '''
    Enables faster pymongo.MongoClient shutdown
    '''
    import pymongo
    try:
        pex = pymongo.periodic_executor.PeriodicExecutor
    except AttributeError:
        # Hotfix for pymongo 4.9.1
        pass
    else:
        original_run = pex._run

        def patched_run(self):
            assert self._min_interval
            self._min_interval = 0.02
            return original_run(self)

        pex._run = patched_run

    try:
        yield
    finally:
        #pex._run = original_run
        # Looks like recent versions of PyMongo have multiple places where
        # PeriodicExecutor is instantiated, sometimes long after MongoClient
        # __init__ is finished.
        # The easiest solution is to just keep the patch in place for the rest
        # of the process lifetime.
        # It is expected that this library (instant-mongo) is used for testing
        # or development purposes anyway, and unlikely to be used in production.
        pass


def tcp_conns_accepted_on_port(port, host='127.0.0.1'):
    import socket
    try:
        c = socket.create_connection((host, port), timeout=0.1)
    except socket.timeout:
        return False
    except OSError as e:
        if e.errno not in (111, 61):
            # re-raise exception if it is not Connection Refused
            raise Exception('Unexpected exception: {!r}'.format(e)) from e
        return False
    else:
        c.close()
        return True
