#!/usr/bin/env python3
"""Generate Cloudflare _redirects for latest BubbleHub release assets."""

from __future__ import annotations

import json
import sys
import urllib.request

LATEST_RELEASE_API = "https://api.github.com/repos/bublhub/BubbleHub/releases/latest"
LATEST_RELEASE_PAGE = "https://github.com/bublhub/BubbleHub/releases/latest"
BRAND_ASSET_KEYWORD = "bubblehub"


def fetch_latest_release() -> dict:
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "bubblehub-website",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def pick_asset(assets: list[dict], extension: str) -> dict | None:
    candidates = [
        asset
        for asset in assets
        if asset.get("name", "").lower().endswith(extension)
        and BRAND_ASSET_KEYWORD in asset.get("name", "").lower()
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

    redirects = "\n".join(
        [
            "/install.sh https://github.com/bublhub/BubbleHub/releases/latest/download/install.sh 302",
            "/install.ps1 https://github.com/bublhub/BubbleHub/releases/latest/download/install.ps1 302",
            f"/download/linux* {download_url(linux)} 302",
            f"/download/windows* {download_url(windows)} 302",
            "",
        ]
    )

    output_path = sys.argv[1] if len(sys.argv) > 1 else "_redirects"
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(redirects)

    print(f"Wrote {output_path}")
    print(f"  linux -> {download_label(linux)}")
    print(f"  windows -> {download_label(windows)}")
    return 0


def download_url(asset: dict | None) -> str:
    if asset:
        return asset["browser_download_url"]

    return LATEST_RELEASE_PAGE


def download_label(asset: dict | None) -> str:
    if asset:
        return asset["name"]

    return "latest release page"


if __name__ == "__main__":
    raise SystemExit(main())
