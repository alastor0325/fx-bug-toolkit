"""Small HTTPS GET helper for the triage scripts.

Inside Claude Code's macOS Bash sandbox, traffic goes through a local proxy that
can drop the last few KB of a reply when the server closes the connection right
after sending it; Bugzilla's REST replies came back cut off after about 5 KB.
Asking for gzip keeps replies small, and a kept-alive connection isn't closed
mid-flush, so they arrive whole. A cut-off reply is retried, then raised.
Honors HTTPS_PROXY, including credentials (the sandbox sets both).
"""

import base64
import gzip
import http.client
import os
import ssl
import urllib.parse

UA = "fx-bug-toolkit-triage"


def proxy_for(env=None):
    """(host, port, tunnel headers) of the HTTPS proxy in the environment, or None."""
    env = os.environ if env is None else env
    value = env.get("HTTPS_PROXY") or env.get("https_proxy") or ""
    if not value:
        return None
    parts = urllib.parse.urlsplit(value if "://" in value else "http://" + value)
    if not parts.hostname:
        return None
    headers = {}
    if parts.username is not None:
        user = urllib.parse.unquote(parts.username)
        password = urllib.parse.unquote(parts.password or "")
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        headers["Proxy-Authorization"] = f"Basic {token}"
    return parts.hostname, parts.port or 8080, headers


def decode_body(body, encoding, limit):
    """Decompress a gzip body; return at most limit + 1 bytes."""
    if (encoding or "").lower() == "gzip":
        body = gzip.decompress(body)
    return body[: limit + 1]


def _get_once(url, limit, timeout):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError(f"https URLs only: {url}")
    port = parts.port or 443
    context = ssl.create_default_context()
    proxy = proxy_for()
    if proxy:
        conn = http.client.HTTPSConnection(proxy[0], proxy[1], timeout=timeout, context=context)
        conn.set_tunnel(parts.hostname, port, headers=proxy[2])
    else:
        conn = http.client.HTTPSConnection(parts.hostname, port, timeout=timeout, context=context)
    try:
        target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        conn.request("GET", target, headers={
            "User-Agent": UA, "Accept": "application/json, */*",
            "Accept-Encoding": "gzip", "Connection": "keep-alive"})
        resp = conn.getresponse()
        body = resp.read()  # raises IncompleteRead when cut off
        if resp.status != 200:
            raise OSError(f"HTTP {resp.status} for {url}")
        return decode_body(body, resp.getheader("Content-Encoding"), limit)
    finally:
        conn.close()


def get(url, limit=64 * 1024 * 1024, timeout=120, attempts=3):
    """GET url and return at most limit + 1 bytes, retrying cut-off replies."""
    for attempt in range(attempts):
        try:
            return _get_once(url, limit, timeout)
        except (http.client.IncompleteRead, ConnectionError, TimeoutError, EOFError):
            if attempt == attempts - 1:
                raise
