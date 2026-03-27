#!/usr/bin/env python3
"""
IronLogic Web-JSON Debug Server

This is a simple HTTP server that logs all requests from the controller
and responds according to the Web-JSON protocol.
Use it to debug communication issues before configuring the integration.

Usage:
    python debug_server.py

Then point your controller to: http://<IP_OF_THIS_MACHINE>:8000/

The server will save all incoming requests as JSON files in the current directory.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


class DebugHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logging.info(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        logging.info(f"GET request: {self.path}")
        self._send_response()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        logging.info(f"POST request: {self.path}")
        logging.info(f"Headers: {self.headers}")
        logging.info(f"Body: {body}")

        filename = f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(
                {
                    "time": datetime.now().isoformat(),
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": body,
                },
                f,
                indent=2,
            )

        self._send_response()

    def _send_response(self):
        response = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "interval": 30,
            "messages": [],
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8000), DebugHandler)
    logging.info("Starting IronLogic Web-JSON debug server on port 8000...")
    logging.info("Point your controller to: http://<IP>:8000/")
    server.serve_forever()
