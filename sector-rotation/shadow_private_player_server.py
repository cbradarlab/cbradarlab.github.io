#!/usr/bin/env python3
"""Personal SHADOW player. Loopback only; expose via authenticated Tailscale Serve."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "data" / "stocks.json"
FEED = Path(os.environ.get("SECTOR_PRIVATE_FEED", "sector_minute_aggregate_shadow.json")).resolve()
PLAYER = ROOT / "shadow_player_online.html"
ROUTES = {
    "/": (PLAYER, "text/html; charset=utf-8"),
    "/shadow_player_online.html": (PLAYER, "text/html; charset=utf-8"),
    "/data/stocks.json": (MASTER, "application/json; charset=utf-8"),
    "/data/sector_minute_latest.json": (FEED, "application/json; charset=utf-8"),
}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path not in ROUTES:
            self.send_error(404)
            return
        file, content_type = ROUTES[path]
        if path == "/data/sector_minute_latest.json":
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                if data.get("publish_permitted") is not False or not data.get("frames"):
                    raise ValueError("Expected private SHADOW sample frames")
            except (OSError, ValueError, json.JSONDecodeError):
                self.send_error(503, "Private feed unavailable")
                return
        try:
            body = file.read_bytes()
        except OSError:
            self.send_error(503, "Required file unavailable")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(body)

def main():
    port = int(os.environ.get("SECTOR_PLAYER_PORT", "8765"))
    print(f"Private SHADOW player: http://127.0.0.1:{port}/", flush=True)
    print("Loopback only. Use authenticated Tailscale Serve; NEVER use Funnel.", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

if __name__ == "__main__":
    main()
