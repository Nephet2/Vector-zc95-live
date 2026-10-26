"""Vector ZC95 0.6: local MFP mapping backend; browser owns Bluetooth output."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import socket
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser
import uuid
from tcode import parse_message
from websocket_input import WebSocketInput

ROOT = Path(__file__).resolve().parent
from engine import Engine, defaults, crossover_defaults, validate, axis_value

class LocalTCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

class MFPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        sock.settimeout(0.5)
        source=uuid.uuid4().hex
        try:
            try:
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,1)
                if hasattr(socket,'SIO_KEEPALIVE_VALS'):sock.ioctl(socket.SIO_KEEPALIVE_VALS,(1,2000,1000))
            except (OSError,AttributeError):pass
            first = b''
            while not first:
                try: first = sock.recv(4096)
                except socket.timeout: continue
                if not first: return
            if first.startswith(b'G'):
                self.server.engine.link_open(source,'WebSocket')
                ws = WebSocketInput(sock, lambda: True, first, lambda:self.server.engine.link_alive(source))
                if ws.handshake():
                    ws.receive(lambda text: self.server.engine.ingest(text, 'WebSocket',source))
                return
            self.server.engine.link_open(source,'TCP')
            buf = first
            while True:
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    self.server.engine.ingest(line.decode('ascii', errors='ignore'), 'TCP',source)
                if len(buf) > 65536: return
                try: data = sock.recv(4096)
                except socket.timeout:
                    self.server.engine.link_alive(source);continue
                if not data:
                    if buf: self.server.engine.ingest(buf.decode('ascii', errors='ignore'), 'TCP',source)
                    return
                self.server.engine.link_alive(source)
                buf += data
        except (OSError, ValueError, EOFError):
            return
        finally:self.server.engine.link_close(source)

class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.server.engine.ingest(self.request[0].decode('ascii', errors='ignore'), 'UDP')

class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def send(self, status, data, kind='application/json'):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)
    def local(self):
        host = self.headers.get('Host', '')
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        if host not in allowed: return False
        origin = self.headers.get('Origin')
        return not origin or origin in {'http://'+h for h in allowed}
    def do_GET(self):
        if not self.local(): return self.send(403, {'error':'Local access only'})
        if self.path == '/api/state':
            data = self.server.engine.snapshot()
            data['mfp_port'] = self.server.mfp_port
            return self.send(200, data)
        if self.path in ('/wifi.js','/patterns.js','/vector_wifi.lua'):
            name=self.path[1:]
            return self.send(200, (ROOT/name).read_bytes(), 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/plain; charset=utf-8')
        if self.path == '/ribbon.js':
            return self.send(200, (ROOT/'ribbon.js').read_bytes(), 'text/javascript; charset=utf-8')
        if self.path == '/editor.js':
            return self.send(200, (ROOT/'editor.js').read_bytes(), 'text/javascript; charset=utf-8')
        if self.path == '/curves.js':
            return self.send(200, (ROOT/'curves.js').read_bytes(), 'text/javascript; charset=utf-8')
        if self.path == '/bluetooth.js':
            return self.send(200, (ROOT/'bluetooth.js').read_bytes(), 'text/javascript; charset=utf-8')
        if self.path in ('/', '/index.html'):
            return self.send(200, (ROOT/'index.html').read_bytes(), 'text/html; charset=utf-8')
        self.send(404, {'error':'Not found'})
    def do_POST(self):
        if not self.local(): return self.send(403, {'error':'Local access only'})
        try:
            n = int(self.headers.get('Content-Length', 0))
            if not 0 < n <= 32768: raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(n))
            if self.path == '/api/config': self.server.engine.configure(data)
            elif self.path == '/api/action': self.server.engine.action(data['action'])
            else: return self.send(404, {'error':'Not found'})
            self.send(200, {'ok': True})
        except (ValueError, KeyError, TypeError, OSError) as e:
            self.send(400, {'error':str(e)})

def make_servers(engine, web_port, mfp_port):
    servers = []
    try:
        for cls, handler, port in [(LocalTCP, MFPHandler, mfp_port),
                (socketserver.ThreadingUDPServer, UDPHandler, mfp_port),
                (ThreadingHTTPServer, WebHandler, web_port)]:
            s = cls(('127.0.0.1', port), handler)
            s.engine, s.mfp_port = engine, mfp_port
            servers.append(s)
        return servers
    except OSError:
        for s in servers: s.server_close()
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--web-port', type=int, default=8766)
    ap.add_argument('--mfp-port', type=int, default=12355)
    ap.add_argument('--no-browser', action='store_true')
    args = ap.parse_args()
    settings=ROOT/'settings-zc95-v3.json'
    if not settings.exists() and (ROOT/'settings-zc95-v2.json').exists():
        import shutil
        shutil.copyfile(ROOT/'settings-zc95-v2.json',settings)
    engine = Engine(settings)
    try: servers = make_servers(engine, args.web_port, args.mfp_port)
    except OSError as e:
        print('Cannot start listener:', e, '\nClose the other Vector ZC95 window or choose different ports.')
        return 1
    for s in servers: threading.Thread(target=s.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{args.web_port}/'
    print('Vector ZC95 0.8.2 - continuous full configured power range; starts disarmed\n'+url)
    print(f'MFP: ws://127.0.0.1:{args.mfp_port}/ws (or TCP/UDP on the same port)')
    print('Keep this window open. Ctrl+C closes the app.')
    if not args.no_browser: webbrowser.open(url)
    try:
        while True: time.sleep(0.5)
    except KeyboardInterrupt: pass
    finally:
        for s in servers: s.shutdown(); s.server_close()
    return 0

if __name__ == '__main__': raise SystemExit(main())
