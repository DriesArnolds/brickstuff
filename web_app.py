#!/usr/bin/env python3
"""Simple web page to look up Rebrickable part details by part number."""

from __future__ import annotations

import html
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from fetch_rebrickable import fetch_path, ssl_fix_hint


HTML_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Rebrickable Part Lookup</title>
    <style>
      body {
        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        margin: 2rem;
        background: #f6f7fb;
        color: #1f2933;
      }
      .container {
        max-width: 760px;
        margin: 0 auto;
        background: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(31, 41, 51, 0.08);
      }
      h1 {
        margin-top: 0;
      }
      form {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        margin-bottom: 1.5rem;
      }
      input[type="text"] {
        flex: 1 1 260px;
        padding: 0.65rem 0.75rem;
        border: 1px solid #cbd2d9;
        border-radius: 8px;
        font-size: 1rem;
      }
      button {
        padding: 0.65rem 1.4rem;
        background: #2563eb;
        border: none;
        color: white;
        border-radius: 8px;
        font-size: 1rem;
        cursor: pointer;
      }
      button:hover {
        background: #1d4ed8;
      }
      .status {
        margin-bottom: 1rem;
        color: #52616b;
      }
      pre {
        background: #f0f4f8;
        padding: 1rem;
        border-radius: 8px;
        overflow-x: auto;
      }
      .error {
        color: #b42318;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <h1>Rebrickable Part Lookup</h1>
      <p class="status">Enter a part number to fetch details from the Rebrickable V3 API.</p>
      <form method="get" action="/">
        <input
          type="text"
          name="part_num"
          placeholder="e.g. 3001"
          value="__PART_VALUE__"
          required
        />
        <button type="submit">Look up part</button>
      </form>
      __CONTENT__
    </div>
  </body>
</html>
"""


class RebrickableHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        part_num = (query.get("part_num") or [""])[0].strip()

        content = ""
        if part_num:
            api_key = os.environ.get("REBRICKABLE_API_KEY")
            if not api_key:
                content = "<p class=\"error\">REBRICKABLE_API_KEY is not set.</p>"
            else:
                try:
                    data = fetch_path(
                        f"lego/parts/{part_num}/",
                        {},
                        api_key,
                    )
                    formatted = html.escape(
                        json_dumps(data),
                        quote=False,
                    )
                    content = f"<pre>{formatted}</pre>"
                except Exception as exc:  # pragma: no cover - basic handler
                    detail = str(exc)
                    if "CERTIFICATE_VERIFY_FAILED" in detail:
                        detail = ssl_fix_hint()
                    content = (
                        "<p class=\"error\">"
                        f"Failed to fetch data: {html.escape(detail)}"
                        "</p>"
                    )

        page = (
            HTML_PAGE.replace("__PART_VALUE__", html.escape(part_num))
            .replace("__CONTENT__", content)
        )
        encoded = page.encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def json_dumps(payload: object) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True)


def run_server(host: str, port: int) -> None:
    server = HTTPServer((host, port), RebrickableHandler)
    print(f"Serving on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server("0.0.0.0", 8000)
