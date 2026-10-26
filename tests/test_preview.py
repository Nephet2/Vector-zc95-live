import base64
import copy
import json
import io
from pathlib import Path
import socket
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from server import Engine, MFPHandler, UDPHandler, WebHandler, make_servers, defaults
from tcode import parse_message
from engine import crossover_defaults, crossover_weights, validate_cross, axis_speed

class Clock:
    now = 100.0
    def __call__(self): return self.now

class FakeSocket:
    def __init__(self, packets):self.packets=list(packets);self.sent=b''
    def settimeout(self,_):pass
    def recv(self,n):
        if not self.packets:return b''
        p=self.packets.pop(0)
        if len(p)>n:self.packets.insert(0,p[n:]);p=p[:n]
        return p
    def sendall(self,b):self.sent+=b

def frame(data, opcode=1):
    p=data.encode();mask=b'abcd'
    return bytes([0x80|opcode,0x80|len(p)])+mask+bytes(b^mask[i%4] for i,b in enumerate(p))

class TransportTests(unittest.TestCase):
    def test_split_tcp_lines_and_udp(self):
        e=Engine();s=FakeSocket([b'L050',b'00 L1',b'2500\nL07500\n'])
        MFPHandler(s,('127.0.0.1',1),SimpleNamespace(engine=e))
        self.assertEqual(e.count,3);self.assertEqual(e.snapshot()['axes']['L0']['value'],.75)
        UDPHandler((b'L09000',None),('127.0.0.1',1),SimpleNamespace(engine=e))
        self.assertEqual(e.transport,'UDP');self.assertEqual(e.count,4)
    def test_websocket_handshake_and_masked_tcode(self):
        header=(b'GET /ws HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n'
                b'Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
                b'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n')
        s=FakeSocket([header+frame('L01234 L15678')+frame('',8)])
        e=Engine();MFPHandler(s,('127.0.0.1',1),SimpleNamespace(engine=e))
        self.assertIn(b'101 Switching Protocols',s.sent);self.assertEqual(e.count,2)
        self.assertEqual(e.transport,'WebSocket')

class HeartbeatTests(unittest.TestCase):
    def test_websocket_ping_liveness_and_dead_peer(self):
        from unittest.mock import patch
        from websocket_input import WebSocketInput
        class Peer(FakeSocket):
            def __init__(self):super().__init__([]);self.first=True
            def recv(self,n):
                if self.first:self.first=False;raise socket.timeout()
                return b'x'
        clock=[0.];alive=[];peer=Peer()
        with patch('websocket_input.time.monotonic',lambda:clock[0]):
            ws=WebSocketInput(peer,lambda:True,b'',lambda:alive.append(True))
            clock[0]=2.5;self.assertEqual(ws._read(1),b'x')
            self.assertEqual(alive,[True]);self.assertEqual(peer.sent[0],0x89)
            peer.first=True;clock[0]=11
            with self.assertRaises(TimeoutError):ws._read(1)

class LocalIntegrationTests(unittest.TestCase):
    def test_http_handlers_without_network(self):
        e=Engine(); h=object.__new__(WebHandler)
        h.server=SimpleNamespace(engine=e,server_port=8766,mfp_port=12355)
        h.headers={'Host':'127.0.0.1:8766'}
        received=[];h.send=lambda *args:received.append(args)
        h.path='/api/state';h.do_GET()
        self.assertEqual(received[-1][0],200)
        self.assertFalse(received[-1][1]['hardware_output'])
        body=b'{"action":"neutral"}'
        h.path='/api/action';h.rfile=io.BytesIO(body);h.headers['Content-Length']=str(len(body));h.do_POST()
        self.assertTrue(e.neutral)
        h.headers['Origin']='http://elsewhere.invalid';h.do_POST()
        self.assertEqual(received[-1][0],403)
        h.headers={'Host':'127.0.0.1:8766','Content-Length':'2'}
        h.path='/api/config';h.rfile=io.BytesIO(b'[]');h.do_POST()
        self.assertEqual(received[-1][0],400)

    def test_http_and_real_udp(self):
        e=Engine()
        try: servers=make_servers(e,0,0)
        except OSError as ex:self.skipTest('Loopback sockets unavailable: '+str(ex))
        for s in servers:threading.Thread(target=s.serve_forever,daemon=True).start()
        web=servers[2];base='http://127.0.0.1:'+str(web.server_port)
        try:
            try:
                page=urlopen(base,timeout=3).read()
            except URLError as ex:
                if isinstance(ex.reason,PermissionError):
                    self.skipTest('Loopback connections blocked by execution environment')
                raise
            self.assertIn(b'Vector ZC95',page)
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.sendto(b'L05000',servers[1].server_address)
            for _ in range(30):
                if e.count:break
                time.sleep(.01)
            data=json.load(urlopen(base+'/api/state'));self.assertEqual(data['count'],1)
            req=Request(base+'/api/action',data=b'{"action":"neutral"}',headers={'Content-Type':'application/json'})
            self.assertTrue(json.load(urlopen(req))['ok']);self.assertTrue(e.neutral)
            req=Request(base+'/api/action',data=b'{"action":"resume"}',headers={'Origin':'http://elsewhere.invalid'})
            with self.assertRaises(HTTPError) as cm:urlopen(req)
            self.assertEqual(cm.exception.code,403)
        finally:
            for s in servers:s.shutdown();s.server_close()

if __name__=='__main__': unittest.main()
