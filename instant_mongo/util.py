import socket
import time


def is_tcp_port_free(port, ip='127.0.0.1'):
    assert isinstance(port, int)
    s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    try:
        try:
            s.bind((ip, port))
        except OSError as e:
            if e.errno in (98, 48):
                # Address already in use
                return False
            else:
                raise Exception('Got unexpected exception from socket bind: {!r}'.format(e)) from e
    finally:
        s.close()
    return True


def get_free_tcp_port(start=9900):
    n = start
    while True:
        if is_tcp_port_free(n):
            return n
        n += 1


class WFATCTimeoutExpiredError (Exception):
    pass


def wait_for_accepting_tcp_conns(port, ip='127.0.0.1', timeout=30):
    t0 = time.monotonic()
    while True:
        try:
            c = socket.create_connection((ip, port), timeout=0.1)
        except socket.timeout:
            pass
        except OSError as e:
            if e.errno not in (111, 61):
                # re-raise exception if it is not Connection Refused
                raise Exception('Unexpected exception: {!r}'.format(e)) from e
        else:
            c.close()
            break

        td = time.monotonic() - t0
        if td > timeout:
            raise WFATCTimeoutExpiredError(
                'Timeout expired while waiting for acceptinh TCP connections on {}:{}'.format(
                    ip, port))
        time.sleep(0.01)

