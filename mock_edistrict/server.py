"""
Mock e-District Kerala Portal HTTP Server
Runs on port 3000 (or OMNIKIOSK_PORTAL_PORT)
Serves static assets, civic forms, downloadable legal pro-formas, knowledge base,
and processes form submissions with dynamic receipt generation.
"""

import http.server
import json
import os
import random
import socketserver
import sys
import threading
import urllib.parse
from datetime import datetime

DEFAULT_PORT = int(os.environ.get("OMNIKIOSK_PORTAL_PORT", "3000"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class EDistrictHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler for e-District Mock Portal."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def log_message(self, format, *args):
        # Quiet server logs for clean test outputs
        if os.environ.get("OMNIKIOSK_DEBUG_SERVER"):
            super().log_message(format, *args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Route root to income certificate form by default
        if path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/forms/income-certificate.html")
            self.end_headers()
            return

        # Health check endpoint
        if path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "OK", "portal": "mock_edistrict"}).encode("utf-8"))
            return

        # Serve static assets, forms, docs, kb, receipts from BASE_DIR
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/submit-application":
            self._handle_submit_application()
        else:
            self.send_error(404, "Endpoint not found")

    def _handle_submit_application(self):
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))

        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        
        # Parse fields from form data
        applicant = "Citizen"
        service = "Income Certificate"
        office = "Village Office Nemom"

        if "application/x-www-form-urlencoded" in content_type:
            params = urllib.parse.parse_qs(raw_body.decode("utf-8", errors="ignore"))
            applicant = params.get("applicant_name", params.get("txtApplicantName", [applicant]))[0]
            service = params.get("service_type", [service])[0]
        elif "multipart/form-data" in content_type:
            # Simple text extraction from multipart body
            body_text = raw_body.decode("latin1", errors="ignore")
            if "txtApplicantName" in body_text:
                parts = body_text.split('name="txtApplicantName"')
                if len(parts) > 1:
                    val = parts[1].split("\r\n\r\n")[1].split("\r\n")[0].strip()
                    if val:
                        applicant = val
            if "ddlVillage" in body_text:
                parts = body_text.split('name="ddlVillage"')
                if len(parts) > 1:
                    val = parts[1].split("\r\n\r\n")[1].split("\r\n")[0].strip()
                    if val:
                        office = f"Village Office {val}"

        # Generate unique tracking ID: KL-EDIST-2026-XXXX
        rand_token = random.randint(1000, 9999)
        tracking_id = f"KL-EDIST-2026-{rand_token}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")

        # Check client Accept header
        accept_header = self.headers.get("Accept", "")
        if "application/json" in accept_header or self.headers.get("X-Requested-With") == "XMLHttpRequest":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response_data = {
                "status": "SUCCESS",
                "tracking_id": tracking_id,
                "timestamp": timestamp,
                "receipt_url": f"/receipts/acknowledgement-slip.html?id={tracking_id}&applicant={urllib.parse.quote(applicant)}&office={urllib.parse.quote(office)}"
            }
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
        else:
            # Browser redirect to acknowledgement receipt
            redirect_url = f"/receipts/acknowledgement-slip.html?id={tracking_id}&applicant={urllib.parse.quote(applicant)}&office={urllib.parse.quote(office)}"
            self.send_response(303)
            self.send_header("Location", redirect_url)
            self.end_headers()


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def start_server(port=DEFAULT_PORT):
    """Starts the mock portal server synchronously."""
    server_address = ("", port)
    with ReusableTCPServer(server_address, EDistrictHandler) as httpd:
        print(f"[Mock e-District] Server running at http://localhost:{port}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Mock e-District] Server stopped.")


def start_server_background(port=DEFAULT_PORT):
    """Starts the mock portal in a background thread for tests."""
    server_address = ("", port)
    httpd = ReusableTCPServer(server_address, EDistrictHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    return httpd, server_thread


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    start_server(port)
