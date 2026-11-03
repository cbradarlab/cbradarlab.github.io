#!/usr/bin/env python3
"""Read-only, true headless-browser smoke test: browser -> TWSE official source.
No external publishing, secrets, local output files, or simulated quote fixtures.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import functools
import shutil
import subprocess
import threading

root = Path("sector-rotation").resolve()
browser = shutil.which("google-chrome") or shutil.which("chromium")
if not browser:
    raise SystemExit("BROWSER_HOLD: headless Chrome not installed on runner")

server = ThreadingHTTPServer(
    ("127.0.0.1", 0),
    functools.partial(SimpleHTTPRequestHandler, directory=str(root)),
)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    url = f"http://127.0.0.1:{server.server_port}/shadow_twse_sector_direct.html"
    run = subprocess.run(
        [browser, "--headless", "--no-sandbox", "--disable-gpu",
         "--disable-dev-shm-usage", "--no-first-run",
         "--virtual-time-budget=12000", "--dump-dom", url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=45, check=False,
    )
    dom = run.stdout
    loaded = "已載入 " in dom and "類指數" in dom and "分鐘" in dom
    sector_nodes = dom.count('class="item"')
    print("BROWSER_SUMMARY", {
        "chrome_exit": run.returncode,
        "source_loaded": loaded,
        "rendered_sectors": sector_nodes,
        "has_271_minute_steps": "271 分鐘" in dom,
        "no_price_values_recorded": True,
    })
    if run.returncode != 0 or not loaded or sector_nodes < 20 or "271 分鐘" not in dom:
        print("BROWSER_HOLD: browser did not complete real TWSE source render")
        # Don't print DOM: it contains original market index values.
        print("CHROME_DIAGNOSTIC", run.stderr[-400:])
        raise SystemExit(2)
    print("BROWSER_PASS_REAL_TWSE_SOURCE")
finally:
    server.shutdown()
