from errno import ECONNREFUSED
from pathlib import Path
import pymongo
from threading import enumerate as enumerate_threads


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
        if db_name in ('admin', 'config', 'local'):
            continue
        client.drop_database(db_name)


def drop_all_collections(db):
    for c_name in sorted(list_collection_names(db)):
        if c_name.startswith('system.'):
            continue
        db[c_name].drop()


def tcp_conns_accepted_on_port(port, host='127.0.0.1'):
    import socket
    try:
        c = socket.create_connection((host, port), timeout=0.1)
    except socket.timeout:
        return False
    except OSError as e:
        if e.errno != ECONNREFUSED:
            # re-raise exception if it is not Connection Refused
            raise Exception(f'Unexpected exception: {e!r}') from e
        return False
    else:
        c.close()
        return True


def join_pymongo_threads():
    '''
    PyMongo maintains threads for replica set monitoring.
    But client.close() doesn't wait for them to finish.
    So we need to join them manually.
    '''
    for t in enumerate_threads():
        if t.name.startswith("pymongo_"):
            t.join(timeout=10)
