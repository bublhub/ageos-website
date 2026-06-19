#!/usr/bin/env python3
"""Generate Cloudflare _redirects for latest AgeOS release assets."""

from __future__ import annotations

import json
import sys
import urllib.request

LATEST_RELEASE_API = "https://api.github.com/repos/ageos-labs/ageos-runtime/releases/latest"


def fetch_latest_release() -> dict:
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ageos-website",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def pick_asset(assets: list[dict], extension: str) -> dict | None:
    candidates = [
        asset
        for asset in assets
        if asset.get("name", "").lower().endswith(extension)
    ]

    for keyword in ("x64", "amd64"):
        for asset in candidates:
            if keyword in asset.get("name", "").lower():
                return asset

    return candidates[0] if candidates else None


def main() -> int:
    release = fetch_latest_release()
    assets = release.get("assets", [])
    linux = pick_asset(assets, ".deb")
    windows = pick_asset(assets, ".exe")

    if not linux or not windows:
        print("Could not find Linux .deb and Windows .exe assets in latest release.", file=sys.stderr)
        return 1

    redirects = "\n".join(
        [
            "/install.sh https://github.com/ageos-labs/ageos-runtime/releases/latest/download/install.sh 302",
            "/install.ps1 https://github.com/ageos-labs/ageos-runtime/releases/latest/download/install.ps1 302",
            f"/download/linux* {linux['browser_download_url']} 302",
            f"/download/windows* {windows['browser_download_url']} 302",
            "",
        ]
    )

    output_path = sys.argv[1] if len(sys.argv) > 1 else "_redirects"
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(redirects)

    print(f"Wrote {output_path}")
    print(f"  linux -> {linux['name']}")
    print(f"  windows -> {windows['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
