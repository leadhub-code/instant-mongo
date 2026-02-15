from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

from instant_mongo.port_guard import PortGuard


def test_get_available_port():
    with PortGuard() as pg:
        port = pg.get_available_port()
        assert isinstance(port, int)
        assert port > 0
        # The port should be bindable now
        s = socket(AF_INET, SOCK_STREAM)
        s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            s.bind(('127.0.0.1', port))
            s.listen(1)
        finally:
            s.close()


def test_get_available_port_returns_unique_ports():
    with PortGuard() as pg:
        ports = [pg.get_available_port() for _ in range(5)]
        assert len(set(ports)) == len(ports)


def test_get_listening_socket():
    with PortGuard() as pg:
        port, sock = pg.get_listening_socket()
        assert isinstance(port, int)
        # The socket should be listening
        assert sock.fileno() != -1
        sock.close()


def test_skips_occupied_port():
    # Occupy a port so that PortGuard has to skip it
    blocker = socket(AF_INET, SOCK_STREAM)
    try:
        blocker.bind(('127.0.0.1', 18000))
        blocker.listen(1)
        with PortGuard(start_port=18000) as pg:
            port = pg.get_available_port()
            assert port >= 18000
            # Should have skipped the occupied pair
            assert port != 18001
    finally:
        blocker.close()


def test_context_manager_closes_guard_sockets():
    with PortGuard() as pg:
        pg.get_available_port()
        pg.get_available_port()
        guard_sockets = list(pg._guard_sockets)
        assert len(guard_sockets) == 2
    # After exiting context, guard sockets should be closed
    for s in guard_sockets:
        assert s.fileno() == -1


def test_close_clears_guard_sockets_list():
    pg = PortGuard()
    pg.get_available_port()
    assert len(pg._guard_sockets) > 0
    pg.close()
    assert pg._guard_sockets == []
