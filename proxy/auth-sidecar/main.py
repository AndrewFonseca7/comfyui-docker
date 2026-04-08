"""
Auth sidecar for validating Bearer API keys, JWT token exchange,
and cookie-based session authentication.
Used by Caddy's forward_auth directive.
"""

import json
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie

import jwt

KEYS_PATH = os.environ.get("API_KEYS_PATH", "/config/api-keys.json")
SESSION_SECRET = os.environ.get("COMFY_SESSION_SECRET", "")
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", "")  # e.g. ".andrewfonseca.dev", empty for localhost
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

# In-memory nonce tracking: {jti: exp_timestamp}
used_nonces = {}


def load_keys():
    try:
        with open(KEYS_PATH) as f:
            data = json.load(f)
        # Expected format: {"keys": [{"key": "...", "name": "..."}]}
        return {entry["key"]: entry.get("name", "anonymous") for entry in data.get("keys", [])}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def purge_expired_nonces():
    """Remove nonces whose exp timestamp has passed."""
    now = time.time()
    expired = [jti for jti, exp in used_nonces.items() if exp < now]
    for jti in expired:
        del used_nonces[jti]


def validate_jwt(token, check_nonce=True):
    """
    Validate a JWT token and return the decoded payload.
    If check_nonce is True, also verify and record the jti nonce.
    Returns (payload, None) on success, (None, error_message) on failure.
    """
    if not SESSION_SECRET:
        return None, "Session secret not configured"

    try:
        payload = jwt.decode(
            token,
            SESSION_SECRET,
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "jti", "name", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        return None, "Token expired"
    except jwt.InvalidTokenError as e:
        return None, f"Invalid token: {e}"

    # Check issuer
    if payload.get("iss") != "creaturia-api":
        return None, "Invalid issuer"

    if check_nonce:
        jti = payload.get("jti")
        if jti in used_nonces:
            return None, "Nonce already used"
        # Record the nonce with its expiry
        used_nonces[jti] = payload.get("exp", 0)

    return payload, None


class AuthHandler(BaseHTTPRequestHandler):
    keys = None

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/validate":
            self._handle_validate()
        elif path == "/exchange":
            self._handle_exchange()
        elif path == "/validate-cookie":
            self._handle_validate_cookie()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_validate(self):
        """Existing Bearer API key validation -- unchanged."""
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

    def _handle_exchange(self):
        """Token exchange: validate JWT from query param, set session cookie."""
        # Purge expired nonces before processing
        purge_expired_nonces()

        # Caddy forwards the original URI in X-Forwarded-Uri
        forwarded_uri = self.headers.get("X-Forwarded-Uri", "")
        parsed = urlparse(forwarded_uri)
        params = parse_qs(parsed.query)
        token_list = params.get("token", [])

        if not token_list:
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Missing token parameter")
            return

        token = token_list[0]
        payload, error = validate_jwt(token, check_nonce=True)

        if error:
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(error.encode())
            return

        name = payload.get("name", "anonymous")

        self.send_response(200)
        self.send_header("X-User", name)
        cookie_parts = [f"comfy_session={token}", "HttpOnly", "Path=/", "Max-Age=28800"]
        if COOKIE_SECURE:
            cookie_parts.extend(["Secure", "SameSite=None"])
        else:
            cookie_parts.append("SameSite=Lax")
        if COOKIE_DOMAIN:
            cookie_parts.append(f"Domain={COOKIE_DOMAIN}")
        self.send_header("Set-Cookie", "; ".join(cookie_parts))
        self.end_headers()

    def _handle_validate_cookie(self):
        """Validate session from comfy_session cookie."""
        cookie_header = self.headers.get("Cookie", "")
        cookies = SimpleCookie()
        try:
            cookies.load(cookie_header)
        except Exception:
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Invalid cookie")
            return

        morsel = cookies.get("comfy_session")
        if not morsel:
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Missing session cookie")
            return

        token = morsel.value
        payload, error = validate_jwt(token, check_nonce=False)

        if error:
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(error.encode())
            return

        name = payload.get("name", "anonymous")
        self.send_response(200)
        self.send_header("X-User", name)
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress default request logging
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), AuthHandler)
    print(f"Auth sidecar listening on port {port}")
    server.serve_forever()
