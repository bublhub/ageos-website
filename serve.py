#!/usr/bin/env python3
"""Local static server for the AgeOS website."""

from __future__ import annotations

import argparse
import http.server
import socketserver
import webbrowser
from functools import partial
from pathlib import Path


class StaticHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".css": "text/css",
        ".js": "application/javascript",
        ".mp4": "video/mp4",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the AgeOS website locally.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to.")
    parser.add_argument("--port", default=4173, type=int, help="Port to bind to.")
    parser.add_argument("--open", action="store_true", help="Open the site in your browser.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parent
    handler = partial(StaticHandler, directory=str(root))

    with ReusableTCPServer((args.host, args.port), handler) as server:
        url = f"http://{args.host}:{args.port}"
        print(f"Serving AgeOS website at {url}")
        print("Press Ctrl+C to stop.")

        if args.open:
            webbrowser.open(url)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
