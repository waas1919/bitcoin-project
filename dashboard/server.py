#!/usr/bin/env python3
"""Dashboard: http://127.0.0.1:8011  (local only).

A background thread polls both nodes; the page reads /api/state.
"""
import json
import pathlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from node_state import NodeState


class Poller(threading.Thread):
    NODES = ("satoshi", "hal")
    POLL_S = 3

    def __init__(self):
        super().__init__(daemon=True)
        self.nodes = [NodeState(n) for n in self.NODES]
        self.lock = threading.Lock()
        self.state = {"updated": None, "nodes": []}

    def run(self):
        while True:
            snaps = []
            for node in self.nodes:
                try:
                    snaps.append(node.snapshot())
                except Exception as err:    # keep the page alive on any error
                    snaps.append({"node": node.rpc.node, "running": False, "error": str(err)})
            with self.lock:
                self.state = {"updated": time.strftime("%H:%M:%S"), "nodes": snaps}
            time.sleep(self.POLL_S)

    def current(self) -> dict:
        with self.lock:
            return self.state


class Handler(BaseHTTPRequestHandler):
    STATIC_DIR = pathlib.Path(__file__).with_name("static")
    ROUTES = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript")}
    poller = None

    def do_GET(self):
        if self.path == "/api/state":
            self._send(json.dumps(self.poller.current()).encode(), "application/json")
        elif self.path in self.ROUTES:
            name, ctype = self.ROUTES[self.path]
            self._send((self.STATIC_DIR / name).read_bytes(), ctype)
        else:
            self.send_error(404)

    def _send(self, body: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):           # quiet
        pass


class DashboardServer:
    HOST = "127.0.0.1"
    PORT = 8011

    def run(self):
        Handler.poller = Poller()
        Handler.poller.start()
        print(f"dashboard on http://{self.HOST}:{self.PORT}", flush=True)
        ThreadingHTTPServer((self.HOST, self.PORT), Handler).serve_forever()


if __name__ == "__main__":
    DashboardServer().run()
