#!/usr/bin/env python3
"""Fetch JSON data from the Rebrickable V3 API."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
from typing import Any
import urllib.parse
import urllib.request

from config_utils import load_env_file

BASE_URL = "https://rebrickable.com/api/v3"


def build_url(path: str, params: dict[str, str]) -> str:
    normalized_path = path.lstrip("/")
    url = f"{BASE_URL}/{normalized_path}"
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"
    return url


def _skip_ssl_verify_enabled() -> bool:
    return os.environ.get("REBRICKABLE_SKIP_SSL_VERIFY", "").lower() in {
        "1",
        "true",
        "yes",
    }


def fetch_json(url: str, api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"key {api_key}", "Accept": "application/json"},
    )

    ssl_context = None
    if _skip_ssl_verify_enabled():
        ssl_context = ssl._create_unverified_context()

    with urllib.request.urlopen(request, context=ssl_context) as response:
        payload = response.read()
        return json.loads(payload)


def parse_params(param_list: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in param_list:
        if "=" not in item:
            raise ValueError(f"Invalid param '{item}'. Use key=value.")
        key, value = item.split("=", 1)
        if not key:
            raise ValueError(f"Invalid param '{item}'. Key cannot be empty.")
        params[key] = value
    return params


def fetch_path(
    path: str,
    params: dict[str, str],
    api_key: str,
) -> dict[str, Any]:
    url = build_url(path, params)
    return fetch_json(url, api_key)


def ssl_fix_hint() -> str:
    return (
        "SSL certificate verification failed. On macOS, run the 'Install Certificates.command' "
        "that ships with your Python install (or use a Python from Homebrew). "
        "Temporary workaround: set REBRICKABLE_SKIP_SSL_VERIFY=1."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch JSON data from the Rebrickable V3 API.",
    )
    parser.add_argument(
        "path",
        help=(
            "API path after /api/v3, e.g. 'lego/sets/10270-1/' or "
            "'lego/sets/'"
        ),
    )
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="Query parameters in key=value form (repeatable).",
    )
    parser.add_argument(
        "--save",
        metavar="FILE",
        help="Optional path to save JSON output.",
    )
    args = parser.parse_args()

    load_env_file(os.environ.get("REBRICKABLE_ENV_FILE", ".env"))

    api_key = os.environ.get("REBRICKABLE_API_KEY")
    if not api_key:
        print("REBRICKABLE_API_KEY environment variable is required.", file=sys.stderr)
        return 1

    try:
        params = parse_params(args.param)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        data = fetch_path(args.path, params, api_key)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        print(f"HTTP error {exc.code}: {detail}", file=sys.stderr)
        return 3
    except ssl.SSLCertVerificationError:
        print(ssl_fix_hint(), file=sys.stderr)
        return 5
    except urllib.error.URLError as exc:
        print(f"Network error: {exc.reason}", file=sys.stderr)
        return 4

    output = json.dumps(data, indent=2, sort_keys=True)
    if args.save:
        with open(args.save, "w", encoding="utf-8") as handle:
            handle.write(output)
        print(f"Saved response to {args.save}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
