from pytest import raises
import socket
import threading

from instant_mongo import util


def test_is_tcp_port_free():
    s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', 0))
        _, available_port = s.getsockname()
        assert isinstance(available_port, int)
        assert util.is_tcp_port_free(available_port) == False
    finally:
        s.close()
    assert util.is_tcp_port_free(available_port) == True


def test_get_free_tcp_port():
    n = util.get_free_tcp_port()
    assert util.is_tcp_port_free(n)


def test_wait_for_accepting_tcp_conns_fail():
    p = util.get_free_tcp_port()
    with raises(util.WFATCTimeoutExpiredError):
        util.wait_for_accepting_tcp_conns(port=p, timeout=0)


def test_wait_for_accepting_tcp_conns_succeeds():
    p = util.get_free_tcp_port()
    s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', p))
        s.listen(8)
        threading.Thread(target=s.accept).start()
        util.wait_for_accepting_tcp_conns(port=p)
    finally:
        s.close()
