#!/usr/bin/env python3
"""Simple web page to look up Rebrickable part details by part number."""

from __future__ import annotations

import html
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from config_utils import load_env_file
from fetch_rebrickable import fetch_path, ssl_fix_hint


PART_VALUE_TOKEN = "__PART_VALUE__"
CONTENT_TOKEN = "__CONTENT__"
ENV_FILE = os.environ.get("REBRICKABLE_ENV_FILE", ".env")

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
        max-width: 880px;
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
      .result-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 1rem;
        border: 1px solid #d9e2ec;
        border-radius: 8px;
        overflow: hidden;
      }
      .result-table th,
      .result-table td {
        padding: 0.7rem 0.8rem;
        text-align: left;
        border-bottom: 1px solid #d9e2ec;
        vertical-align: top;
      }
      .result-table th {
        width: 220px;
        background: #f0f4f8;
        color: #334e68;
      }
      .result-table tr:last-child th,
      .result-table tr:last-child td {
        border-bottom: none;
      }
      details {
        margin-top: 1rem;
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


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def render_part_table(part: dict[str, Any]) -> str:
    rows: list[tuple[str, str]] = [
        ("Part Number", _fmt(part.get("part_num"))),
        ("Name", _fmt(part.get("name"))),
        ("Category", _fmt((part.get("part_cat") or {}).get("name"))),
        ("Part URL", _fmt(part.get("part_url"))),
        ("Print of", _fmt(part.get("print_of"))),
        ("Part Material", _fmt(part.get("part_material"))),
        ("Year From", _fmt(part.get("year_from"))),
        ("Year To", _fmt(part.get("year_to"))),
    ]

    external_ids = part.get("external_ids")
    if isinstance(external_ids, dict) and external_ids:
        rows.append(("External IDs", _fmt(external_ids)))

    table_rows = "".join(
        "<tr>"
        f"<th>{html.escape(label)}</th>"
        f"<td>{html.escape(value)}</td>"
        "</tr>"
        for label, value in rows
        if value
    )

    raw_json = html.escape(json.dumps(part, indent=2, sort_keys=True), quote=False)
    return (
        '<h2 style="margin-bottom:0.4rem;">Part details</h2>'
        '<table class="result-table">'
        f"{table_rows}"
        "</table>"
        "<details><summary>Show raw JSON</summary>"
        f"<pre>{raw_json}</pre>"
        "</details>"
    )


def render_page(part_num: str, content: str) -> str:
    """Render the HTML page without calling str.format on CSS braces."""
    return (
        HTML_PAGE.replace(PART_VALUE_TOKEN, html.escape(part_num))
        .replace(CONTENT_TOKEN, content)
    )


class RebrickableHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        part_num = (query.get("part_num") or [""])[0].strip()

        content = ""
        if part_num:
            load_env_file(ENV_FILE)
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
                    content = render_part_table(data)
                except Exception as exc:  # pragma: no cover - basic handler
                    detail = str(exc)
                    if "CERTIFICATE_VERIFY_FAILED" in detail:
                        detail = ssl_fix_hint()
                    content = (
                        "<p class=\"error\">"
                        f"Failed to fetch data: {html.escape(detail)}"
                        "</p>"
                    )

        page = render_page(part_num, content)
        encoded = page.encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_server(host: str, port: int) -> None:
    server = HTTPServer((host, port), RebrickableHandler)
    print(f"Serving on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    load_env_file(ENV_FILE)
    run_server("0.0.0.0", 8000)
