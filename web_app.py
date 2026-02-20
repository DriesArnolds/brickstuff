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
      .color-swatch {
        display: inline-block;
        width: 1rem;
        height: 1rem;
        border: 1px solid #9aa5b1;
        border-radius: 4px;
        vertical-align: middle;
        margin-right: 0.5rem;
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








def _first_present(entry: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in entry and entry.get(key) not in (None, ""):
            return entry.get(key)
    return None

def _color_field(color_entry: dict[str, Any], field: str) -> str:
    """Best-effort extraction for color fields across API payload shapes."""
    value = color_entry.get(field)
    if value not in (None, ""):
        return _fmt(value)

    nested = color_entry.get("color")
    if isinstance(nested, dict):
        nested_value = nested.get(field)
        if nested_value not in (None, ""):
            return _fmt(nested_value)

    # Alternate key names seen in some payloads
    aliases = {
        "id": ["color_id", "id_color", "colour_id"],
        "name": ["color_name", "colour_name"],
        "rgb": ["color_rgb", "rgb_hex", "hex", "colour_rgb"],
    }
    for alias in aliases.get(field, []):
        alias_val = color_entry.get(alias)
        if alias_val not in (None, ""):
            return _fmt(alias_val)

    return ""



def _normalize_rgb(value: str) -> str:
    rgb = value.strip().lstrip("#")
    if len(rgb) == 3:
        rgb = "".join(ch * 2 for ch in rgb)
    if len(rgb) != 6:
        return ""
    if any(ch not in "0123456789abcdefABCDEF" for ch in rgb):
        return ""
    return rgb.upper()

def _safe_link(url: str, label: str) -> str:
    safe_url = html.escape(url, quote=True)
    safe_label = html.escape(label)
    return (
        f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">'
        f"{safe_label}</a>"
    )


def _external_url(source: str, ext_id: str) -> str | None:
    source_key = source.strip().lower()
    if source_key == "bricklink":
        return f"https://www.bricklink.com/v2/catalog/catalogitem.page?P={ext_id}"
    if source_key == "brickowl":
        return f"https://www.brickowl.com/catalog/lego-part-{ext_id}"
    if source_key == "lego":
        return f"https://www.lego.com/en-us/pick-and-build/pick-a-brick?query={ext_id}"
    if source_key == "ldraw":
        return f"https://library.ldraw.org/library/unofficial/{ext_id}.dat"
    if source_key == "brickset":
        return f"https://brickset.com/parts/design-{ext_id}"
    return None


def _render_external_ids_html(external_ids: dict[str, Any]) -> str:
    chunks: list[str] = []
    for source, raw_ids in external_ids.items():
        ids = raw_ids if isinstance(raw_ids, list) else [raw_ids]
        links: list[str] = []
        for item in ids:
            id_text = str(item)
            url = _external_url(source, id_text)
            if url:
                links.append(_safe_link(url, id_text))
            else:
                links.append(html.escape(id_text))

        if links:
            safe_source = html.escape(str(source))
            chunks.append(f"<div><strong>{safe_source}:</strong> {', '.join(links)}</div>")

    return "".join(chunks)

def render_part_table(part: dict[str, Any], colors_payload: dict[str, Any] | None = None) -> str:
    part_url = _fmt(part.get("part_url"))
    part_url_html = _safe_link(part_url, part_url) if part_url else ""

    rows: list[tuple[str, str, bool]] = [
        ("Part Number", _fmt(part.get("part_num")), False),
        ("Name", _fmt(part.get("name")), False),
        ("Category", _fmt((part.get("part_cat") or {}).get("name")), False),
        ("Part URL", part_url_html, True),
        ("Print of", _fmt(part.get("print_of")), False),
        ("Part Material", _fmt(part.get("part_material")), False),
        ("Year From", _fmt(part.get("year_from")), False),
        ("Year To", _fmt(part.get("year_to")), False),
    ]

    external_ids = part.get("external_ids")
    if isinstance(external_ids, dict) and external_ids:
        rows.append(("External IDs", _render_external_ids_html(external_ids), True))

    table_rows = "".join(
        "<tr>"
        f"<th>{html.escape(label)}</th>"
        f"<td>{value if is_html else html.escape(value)}</td>"
        "</tr>"
        for label, value, is_html in rows
        if value
    )

    part_img_url = _fmt(part.get("part_img_url"))
    image_html = ""
    if part_img_url:
        safe_img_url = html.escape(part_img_url, quote=True)
        image_html = (
            '<div style="margin-top:1rem;">'
            '<h3 style="margin-bottom:0.5rem;">Part image</h3>'
            f'<img src="{safe_img_url}" alt="Part image for {html.escape(_fmt(part.get("part_num")))}" '
            'style="max-width:100%; height:auto; border:1px solid #d9e2ec; border-radius:8px;" />'
            "</div>"
        )

    colors_html = render_colors_table(part, colors_payload) if colors_payload else ""

    raw_json = html.escape(json.dumps(part, indent=2, sort_keys=True), quote=False)
    return (
        '<h2 style="margin-bottom:0.4rem;">Part details</h2>'
        '<table class="result-table">'
        f"{table_rows}"
        "</table>"
        f"{image_html}"
        f"{colors_html}"
        "<details><summary>Show raw JSON</summary>"
        f"<pre>{raw_json}</pre>"
        "</details>"
    )






def enrich_colors_with_rgb(
    colors_payload: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    """Fill missing RGB values by querying /lego/colors/{id}/ as a fallback."""
    results = colors_payload.get("results")
    if not isinstance(results, list):
        return colors_payload

    rgb_cache: dict[str, str] = {}
    for entry in results:
        if not isinstance(entry, dict):
            continue
        if _color_field(entry, "rgb"):
            continue

        color_id = _color_field(entry, "id")
        if not color_id:
            continue

        if color_id not in rgb_cache:
            try:
                color_data = fetch_path(f"lego/colors/{color_id}/", {}, api_key)
                rgb_cache[color_id] = _fmt(color_data.get("rgb"))
            except Exception:
                rgb_cache[color_id] = ""

        rgb_value = rgb_cache[color_id]
        if rgb_value:
            entry["rgb"] = rgb_value

    return colors_payload

def render_colors_table(part: dict[str, Any], colors_payload: dict[str, Any]) -> str:
    results = colors_payload.get("results")
    if not isinstance(results, list) or not results:
        return "<p>No available colors returned for this part.</p>"

    part_url = _fmt(part.get("part_url")).rstrip("/")

    rows: list[str] = []
    for color_entry in results:
        if not isinstance(color_entry, dict):
            continue

        color_id = _color_field(color_entry, "id")
        color_name = _color_field(color_entry, "name")
        rgb = _color_field(color_entry, "rgb")

        num_sets = _fmt(
            _first_present(
                color_entry,
                ["num_sets", "sets", "set_count"],
            )
        )
        num_parts = _fmt(
            _first_present(
                color_entry,
                ["num_parts", "parts", "part_count", "quantity", "num_set_parts"],
            )
        )

        if not color_id and not color_name and not rgb and not num_sets and not num_parts:
            continue

        color_name_html = html.escape(color_name)
        if part_url and color_id and color_name:
            color_url = f"{part_url}/{color_id}/"
            color_name_html = _safe_link(color_url, color_name)

        normalized_rgb = _normalize_rgb(rgb)
        swatch = ""
        rgb_text = html.escape(rgb)
        if normalized_rgb:
            safe_rgb = html.escape(normalized_rgb, quote=True)
            swatch = f'<span class="color-swatch" style="background-color: #{safe_rgb};"></span>'
            rgb_text = f"{swatch}#{html.escape(normalized_rgb)}"

        rows.append(
            "<tr>"
            f"<td>{html.escape(color_id)}</td>"
            f"<td>{color_name_html}</td>"
            f"<td>{rgb_text}</td>"
            f"<td>{html.escape(num_sets)}</td>"
            f"<td>{html.escape(num_parts)}</td>"
            "</tr>"
        )

    if not rows:
        return "<p>No available colors returned for this part.</p>"

    return (
        '<h3 style="margin-top:1.5rem; margin-bottom:0.5rem;">Available colors</h3>'
        '<table class="result-table">'
        '<thead><tr><th>ID</th><th>Color</th><th>RGB</th><th>Sets</th><th>Parts</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
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
                    colors_data = fetch_path(
                        f"lego/parts/{part_num}/colors/",
                        {},
                        api_key,
                    )
                    colors_data = enrich_colors_with_rgb(colors_data, api_key)
                    content = render_part_table(data, colors_data)
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
