import http.server
import socketserver

from bcml.util import get_exec_dir


class BcmlRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(get_exec_dir() / "assets"), **kwargs)

    def log_message(self, format, *args):
        pass


def start_server(port: int):
    with socketserver.TCPServer(("", port), BcmlRequestHandler) as httpd:
        httpd.serve_forever()
