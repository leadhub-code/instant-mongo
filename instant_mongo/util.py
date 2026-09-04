from errno import ECONNREFUSED
from logging import getLogger
from pathlib import Path
from socket import create_connection
from struct import pack, unpack
import bson
import pymongo
from threading import enumerate as enumerate_threads


logger = getLogger('instant_mongo')

OP_MSG = 2013  # MongoDB wire protocol opcode (MongoDB 3.6+)


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


def mongo_ping(port, host='127.0.0.1', timeout=0.5):
    '''
    Send the `ping` command to a MongoDB server over a plain socket using
    the wire protocol (OP_MSG) and return True if the server replies with ok=1.

    Unlike MongoClient this starts no background threads, so it can be used
    during start-up without leaving any threads behind (fork safety).

    Any connection, timeout or protocol error results in False - the caller
    is expected to retry until its own deadline.
    '''
    request_id = 1
    body = bson.encode({'ping': 1, '$db': 'admin'})
    # header: messageLength, requestID, responseTo, opCode; then flagBits and
    # a single body section (kind 0) with one BSON document
    request = pack('<iiiiiB', 16 + 4 + 1 + len(body), request_id, 0, OP_MSG, 0, 0) + body
    try:
        with create_connection((host, port), timeout=timeout) as s:
            s.sendall(request)
            length, _, response_to, op_code = unpack('<iiii', _recv_exactly(s, 16))
            if op_code != OP_MSG or response_to != request_id:
                logger.debug('Ping: unexpected reply header (opCode=%r, responseTo=%r)', op_code, response_to)
                return False
            payload = _recv_exactly(s, length - 16)
            # payload: flagBits (4 bytes), section kind (1 byte), BSON document
            if payload[4] != 0:
                logger.debug('Ping: unexpected section kind %r', payload[4])
                return False
            doc_length, = unpack('<i', payload[5:9])
            reply = bson.decode(payload[5:5 + doc_length])
    except (OSError, IndexError, ValueError, bson.errors.InvalidBSON) as e:
        # ValueError also covers struct.error
        logger.debug('Ping to %s:%s failed: %r', host, port, e)
        return False
    if reply.get('ok') != 1:
        logger.debug('Ping: server replied %r', reply)
        return False
    return True


def _recv_exactly(sock, n):
    chunks = []
    while n > 0:
        chunk = sock.recv(n)
        if not chunk:
            raise ConnectionError('connection closed before the whole message was received')
        chunks.append(chunk)
        n -= len(chunk)
    return b''.join(chunks)


def join_pymongo_threads():
    '''
    PyMongo maintains threads for replica set monitoring.
    But client.close() doesn't wait for them to finish.
    So we need to join them manually.
    '''
    for t in enumerate_threads():
        if t.name.startswith("pymongo_"):
            t.join(timeout=10)
