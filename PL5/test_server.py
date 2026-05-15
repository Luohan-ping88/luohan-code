#!/usr/bin/env python3

"""
测试HTTP服务器是否能够正常运行
"""

from http.server import HTTPServer, BaseHTTPRequestHandler

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Hello, World!')

if __name__ == "__main__":
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, TestHandler)
    print('Server running at http://localhost:8000/')
    httpd.serve_forever()
