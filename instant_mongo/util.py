from errno import ECONNREFUSED
from logging import getLogger
from pathlib import Path
from socket import create_connection
from struct import pack, unpack, error as StructError
import bson
import pymongo
from threading import enumerate as enumerate_threads


logger = getLogger('instant_mongo')

OP_MSG = 2013  # MongoDB wire protocol opcode (MongoDB 3.6+)
MAX_MESSAGE_SIZE = 48 * 1024 * 1024  # maxMessageSizeBytes of MongoDB servers


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


def mongo_command(port, command, host='127.0.0.1', timeout=0.5, db='admin'):
    '''
    Send a single command to a MongoDB server over a plain socket using
    the wire protocol (OP_MSG) and return the reply document.

    Unlike MongoClient this starts no background threads, so it can be used
    during start-up without leaving any threads behind (fork safety).

    Any connection, timeout or protocol error results in None - the caller
    is expected to retry until its own deadline.
    '''
    request_id = 1
    body = bson.encode({**command, '$db': db})
    # header: messageLength, requestID, responseTo, opCode; then flagBits and
    # a single body section (kind 0) with one BSON document
    request = pack('<iiiiiB', 16 + 4 + 1 + len(body), request_id, 0, OP_MSG, 0, 0) + body
    try:
        with create_connection((host, port), timeout=timeout) as s:
            s.sendall(request)
            length, _, response_to, op_code = unpack('<iiii', _recv_exactly(s, 16))
            if op_code != OP_MSG or response_to != request_id:
                logger.debug('Unexpected reply header from %s:%s (opCode=%r, responseTo=%r)', host, port, op_code, response_to)
                return None
            # payload: flagBits (4 bytes), section kind (1 byte), BSON document (5+ bytes)
            if not 16 + 4 + 1 + 5 <= length <= MAX_MESSAGE_SIZE:
                logger.debug('Unexpected reply length from %s:%s: %r', host, port, length)
                return None
            payload = _recv_exactly(s, length - 16)
            if payload[4] != 0:
                logger.debug('Unexpected section kind %r in reply from %s:%s', payload[4], host, port)
                return None
            doc_length, = unpack('<i', payload[5:9])
            return bson.decode(payload[5:5 + doc_length])
    except (OSError, IndexError, StructError, bson.errors.InvalidBSON) as e:
        logger.debug('Command %r to %s:%s failed: %r', next(iter(command)), host, port, e)
        return None


def mongo_ping(port, host='127.0.0.1', timeout=0.5):
    '''
    Return True if a MongoDB server on the given port replies to `ping` with ok=1.
    See mongo_command() for details.
    '''
    reply = mongo_command(port, {'ping': 1}, host=host, timeout=timeout)
    return reply is not None and reply.get('ok') == 1


def mongo_server_pid(port, host='127.0.0.1', timeout=0.5):
    '''
    Return the PID of the MongoDB server listening on the given port
    (from `serverStatus`), or None if it cannot be determined.
    See mongo_command() for details.
    '''
    # disable the large sections of serverStatus - only the pid is needed
    command = {'serverStatus': 1, 'metrics': 0, 'wiredTiger': 0, 'tcmalloc': 0, 'locks': 0, 'opLatencies': 0}
    reply = mongo_command(port, command, host=host, timeout=timeout)
    if reply is None or reply.get('ok') != 1:
        return None
    return reply.get('pid')


def _recv_exactly(sock, n):
    chunks = []
    while n > 0:
        chunk = sock.recv(min(n, 1024 * 1024))
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
