#!/usr/bin/env python3
"""Serve the dashboard and proxy local InfluxDB requests without browser CORS."""
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, urlencode
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.abspath(__file__))
INFLUX_HOST = os.getenv("INFLUX_HOST", "127.0.0.1")
INFLUX_PORT = int(os.getenv("INFLUX_PORT", "8086"))


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        # The dashboard is updated in place during field work. Prevent a
        # phone/browser from keeping an older JavaScript bundle that still
        # reports "no live data" after the Pi has been fixed.
        path = urlsplit(self.path).path
        if path in ("", "/") or path.endswith(".html"):
            self.send_header("Cache-Control", "no-store, max-age=0")
        if path == "/api/influx/query":
            # Allow the same dashboard file to be opened from a local
            # file:// tab during field work while keeping the database
            # itself private behind this read-only proxy.
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/api/influx/query":
            self.proxy_query(parse_qs(parsed.query))
            return
        super().do_GET()

    def do_OPTIONS(self):
        if urlsplit(self.path).path == "/api/influx/query":
            self.send_response(204)
            self.end_headers()
            return
        self.send_error(404)

    def proxy_query(self, params):
        db = params.get("db", ["piprobe"])[0]
        query = params.get("q", [""])[0]
        if not query:
            self.send_error(400, "Missing InfluxQL query")
            return
        target = "http://{}:{}/query?{}".format(
            INFLUX_HOST, INFLUX_PORT, urlencode({"db": db, "q": query})
        )
        try:
            with urlopen(Request(target, headers={"Accept": "application/json"}), timeout=5) as response:
                body = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except Exception as exc:
            self.send_error(502, "InfluxDB proxy failed: {}".format(exc))


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "8888"))
    server = ThreadingHTTPServer(("0.0.0.0", port), DashboardHandler)
    print("Trinetra dashboard listening on port {}".format(port), flush=True)
    server.serve_forever()
