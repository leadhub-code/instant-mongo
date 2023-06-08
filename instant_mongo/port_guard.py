import socket


class PortGuard:

    def __init__(self, start_port=9900):
        self._next_port = start_port
        self._guard_sockets = []

    def get_listening_socket(self, bind_host='127.0.0.1'):
        while True:
            assert self._next_port % 2 == 0
            guard_port, app_port = self._next_port, self._next_port + 1
            s_guard = None
            s_app = None
            try:
                s_guard = socket.socket(
                    family=socket.AF_INET,
                    type=socket.SOCK_STREAM)
                s_guard.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s_guard.bind(('127.0.0.1', guard_port))
                s_guard.listen(1)

                s_app = socket.socket(
                    family=socket.AF_INET,
                    type=socket.SOCK_STREAM)
                s_app.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s_app.bind(('127.0.0.1', app_port))
                s_app.listen(1)
            except Exception:
                if s_guard:
                    s_guard.close()
                if s_app:
                    s_app.close()
                self._next_port += 2
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
