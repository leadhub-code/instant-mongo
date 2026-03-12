from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR


class PortGuard:
    """
    Allocate available TCP ports while preventing race conditions.

    Ports are allocated in pairs: a guard port and an application port.
    The guard socket is kept open to prevent the adjacent application port
    from being reused by another process before the caller binds to it.
    But this approach works only if that another process uses the same port
    allocation strategy.

    Use as a context manager to ensure guard sockets are cleaned up.
    """

    def __init__(self, start_port=19000):
        self._start_port = start_port
        self._next_port = start_port
        self._guard_sockets = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_listening_socket(self, bind_host='127.0.0.1'):
        while True:
            assert self._next_port % 2 == 0
            guard_port, app_port = self._next_port, self._next_port + 1
            s_guard = None
            s_app = None
            try:
                s_guard = socket(family=AF_INET, type=SOCK_STREAM)
                s_guard.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
                s_guard.bind((bind_host, guard_port))
                s_guard.listen(1)

                s_app = socket(family=AF_INET, type=SOCK_STREAM)
                s_app.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
                s_app.bind((bind_host, app_port))
                s_app.listen(1)
            except Exception:
                if s_guard:
                    s_guard.close()
                if s_app:
                    s_app.close()
                self._next_port += 2
                if self._next_port >= 65535:
                    self._next_port = self._start_port
                continue
            self._guard_sockets.append(s_guard)
            return (app_port, s_app)

    def get_available_port(self):
        port, sock = self.get_listening_socket()
        sock.close()
        return port

    def close(self):
        for sock in self._guard_sockets:
            sock.close()
        self._guard_sockets = []
