#!/usr/bin/env python3
"""
MaaS per-user key-injecting proxy for the OpenWebUI client.

OpenWebUI calls this proxy server-side (no CORS) for the global connection. With
ENABLE_FORWARD_USER_INFO_HEADERS=true it attaches the logged-in user's identity
as `X-OpenWebUI-User-Email`. This proxy maps that user to their own MaaS sk- key
(one file per user under KEYS_DIR, mounted from a Secret), replaces the
Authorization header, and forwards to the MaaS gateway — so each user's traffic
is metered under their own identity.

Stdlib only (no pip deps) so it runs on a stock UBI python image via a ConfigMap.
Streams responses by framing with Connection: close (works for SSE and JSON).
"""
import os
import ssl
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ["UPSTREAM_BASE_URL"].rstrip("/")          # https://maas.<domain>/<ns>/<isvc>/v1
KEYS_DIR = os.environ.get("KEYS_DIR", "/etc/userkeys")
EMAIL_HEADER = os.environ.get("USER_EMAIL_HEADER", "X-OpenWebUI-User-Email")
# Fallback key used ONLY for unauthenticated model listing (GET /models), so the
# OpenWebUI model dropdown populates even when the backend fetches models without
# a user context. Inference always requires a per-user key (else 403).
DEFAULT_KEY = os.environ.get("DEFAULT_KEY", "")
PORT = int(os.environ.get("PORT", "8000"))

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE   # external gateway cert; key is what authorizes


def key_for(email):
    """email 'user1@domain' -> ('user1', '<sk- key>' or None)."""
    user = (email or "").split("@")[0].strip()
    if not user:
        return None, None
    path = os.path.join(KEYS_DIR, user)
    if os.path.isfile(path):
        with open(path) as fh:
            return user, fh.read().strip()
    return user, None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _err(self, code, msg):
        body = ('{"error": "%s"}' % msg.replace('"', "'")).encode()
        self.close_connection = True
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _do(self, method):
        email = self.headers.get(EMAIL_HEADER, "")
        user, key = key_for(email)
        if not key:
            is_model_list = method == "GET" and self.path.rstrip("/").endswith("/models")
            if is_model_list and DEFAULT_KEY:
                key = DEFAULT_KEY          # allow dropdown to populate, not metered-sensitive
            else:
                return self._err(
                    403, "no MaaS key provisioned for user '%s' (email=%s)"
                    % (user or "?", email or "none"))

        sub = self.path
        if sub.startswith("/v1"):
            sub = sub[len("/v1"):]
        target = UPSTREAM + sub

        length = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(length) if length else None

        req = urllib.request.Request(target, data=data, method=method)
        req.add_header("Authorization", "Bearer " + key)
        for h in ("Content-Type", "Accept"):
            v = self.headers.get(h)
            if v:
                req.add_header(h, v)

        try:
            up = urllib.request.urlopen(req, context=_SSL, timeout=600)
        except urllib.error.HTTPError as e:
            up = e
        except Exception as e:                          # noqa: BLE001
            return self._err(502, "upstream error: %s" % e)

        print("%s %s -> user=%s status=%s" % (method, self.path, user or "-", up.status), flush=True)
        self.close_connection = True
        self.send_response(up.status)
        ct = up.headers.get("Content-Type")
        if ct:
            self.send_header("Content-Type", ct)
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            while True:
                chunk = up.read(2048)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except Exception:                               # noqa: BLE001
            pass

    def do_GET(self):
        self._do("GET")

    def do_POST(self):
        self._do("POST")

    def do_DELETE(self):
        self._do("DELETE")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
