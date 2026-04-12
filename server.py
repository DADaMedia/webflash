#!/usr/bin/env python3
"""WebFlash Server - ESP32 firmware flashing interface"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json
import os
import sys
import subprocess
import urllib.parse

PORT = 8089
SCRIPT_DIR = Path(__file__).parent


class WebFlashHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # List available serial ports
        if self.path == '/api/ports' or self.path == '/flash/api/ports':
            try:
                import glob
                ports = glob.glob('/dev/tty*') + glob.glob('/dev/cu*')
                ports = [p for p in ports if 'USB' in p or 'ACM' in p or 'S' in p]

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'ports': ports[:5]}).encode())
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
                return

        # Serve manifest.json (handle both /manifest.json and /flash/manifest.json)
        if self.path == '/manifest.json' or self.path == '/flash/manifest.json' or self.path.endswith('/manifest.json'):
            try:
                manifest_path = SCRIPT_DIR / 'manifest.json'
                with open(manifest_path, 'r') as f:
                    data = json.load(f)

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
                return
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                return

        # Default: serve static files from directory
        self.directory = str(SCRIPT_DIR)
        super().do_GET()

    def do_POST(self):
        # Handle flash API
        if self.path == '/api/flash' or self.path == '/flash/api/flash':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                build_index = data.get('build_index')
                port = data.get('port', '/dev/ttyUSB0')

                # Load manifest
                manifest_path = SCRIPT_DIR / 'manifest.json'
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)

                build = manifest['builds'][build_index]

                # Build esptool command
                cmd = ['esptool.py', '--chip', 'esp32s3', '--port', port, 'write_flash']
                for part in build['parts']:
                    firmware_path = SCRIPT_DIR / part['path']
                    cmd.extend(['--flash_mode', 'dio', '--flash_freq', '40m'])
                    cmd.extend([str(part['offset']), str(firmware_path)])

                # Run esptool
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                if result.returncode == 0:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': True, 'message': f'{build["name"]} flashed successfully'}).encode())
                else:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': result.stderr}).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
            return

    def end_headers(self):
        # CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def log_message(self, format, *args):
        """Log to stderr"""
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))
        sys.stderr.flush()


def run_server():
    server_address = ('127.0.0.1', PORT)
    httpd = HTTPServer(server_address, WebFlashHandler)
    print(f"WebFlash server running on http://127.0.0.1:{PORT}", file=sys.stderr)
    print(f"Serving files from: {SCRIPT_DIR}", file=sys.stderr)
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
