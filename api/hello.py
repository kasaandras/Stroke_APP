"""Diagnostic: minimal Python function with no third-party deps.

If GET /api/hello returns the JSON below, Vercel's Python runtime is
working on this project and the predict.py issue is specific to that
file. If /api/hello 404s or 500s, the Python runtime itself isn't
deploying on this project.
"""
from http.server import BaseHTTPRequestHandler
import json


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps({
            "message": "Hello from Vercel Python",
            "path": self.path,
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
