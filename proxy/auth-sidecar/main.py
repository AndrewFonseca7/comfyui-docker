"""
Minimal auth sidecar for validating Bearer API keys.
Used by Caddy's forward_auth directive.
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

KEYS_PATH = os.environ.get("API_KEYS_PATH", "/config/api-keys.json")


def load_keys():
    try:
        with open(KEYS_PATH) as f:
            data = json.load(f)
        # Expected format: {"keys": [{"key": "...", "name": "..."}]}
        return {entry["key"]: entry.get("name", "anonymous") for entry in data.get("keys", [])}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


class AuthHandler(BaseHTTPRequestHandler):
    keys = None

    def do_GET(self):
        if self.path != "/validate":
            self.send_response(404)
            self.end_headers()
            return

        # Reload keys on each request (allows hot-reload)
        keys = load_keys()

        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Missing or invalid Authorization header")
            return

        token = auth_header[len("Bearer "):]
        if token in keys:
            self.send_response(200)
            self.send_header("X-User", keys[token])
            self.end_headers()
        else:
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Invalid API key")

    def log_message(self, format, *args):
        # Suppress default request logging
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), AuthHandler)
    print(f"Auth sidecar listening on port {port}")
    server.serve_forever()
