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

class MappingTests(unittest.TestCase):
    def setUp(self): self.clock=Clock(); self.e=Engine(clock=self.clock)
    def settings(self, paired=True):
        rows=defaults()
        for c in rows:
            c['smoothing_ms']=0
            for stem in ('power','frequency','width'):
                c[stem+'_rest_enabled']=False
                c[stem+'_damping_ms']=0
                c[stem+'_mode']='fixed'
        cross=crossover_defaults();cross.update(enabled=paired,smoothing_ms=0)
        return dict(channels=rows,crossover=cross)
    def apply(self,data=None): self.e.configure(data or self.settings())
    def sample(self,x):
        self.e.ingest('L0'+str(round(x*10000)).zfill(4),'test')
        return self.e.snapshot()['channels']
    def test_follow_ab_texture_exact_and_restore(self):
        d=self.settings(False)
        for i,c in enumerate(d['channels']):
            c['frequency_max']=70+i*30;c['width_max']=90+i*40
        for c in d['channels'][1:]:
            c['frequency_follow_ab']=True;c['width_follow_ab']=True
        self.apply(d);rows=self.sample(.5)
        self.assertEqual([r['frequency'] for r in rows],[70,70,70])
        self.assertEqual([r['width'] for r in rows],[90,90,90])
        d['channels'][1]['frequency_follow_ab']=False
        d['channels'][2]['width_follow_ab']=False
        self.apply(d);rows=self.sample(.5)
        self.assertEqual([r['frequency'] for r in rows],[70,100,70])
        self.assertEqual([r['width'] for r in rows],[90,90,170])
        self.e.action('neutral')
        self.assertTrue(all(r['power']==0 for r in self.e.snapshot()['channels']))
        d['channels'][1]['width_follow_ab']='yes'
        with self.assertRaises(ValueError):self.apply(d)

    def test_parse_concatenated_and_interval(self):
        c=parse_message('L05000I1000L17500 V02500\n')
        self.assertEqual([x.axis for x in c], ['L0','L1','V0'])
        self.assertEqual([x.value for x in c], [.5,.75,.25]);self.assertEqual(c[0].interval_ms,1000)
    def test_crossover_reference_table_and_floor_gate(self):
        data=self.settings();data['channels'][0]['power_min']=8;data['channels'][1]['power_min']=8
        self.apply(data)
        for x,w in [(.1,(100,0)),(.4,(100,0)),(.45,(75,25)),(.5,(50,50)),(.55,(25,75)),(.6,(0,100)),(.9,(0,100))]:
            out=self.sample(x)
            self.assertEqual(tuple(c['weight'] for c in out[:2]),w)
            self.assertEqual(tuple(c['power'] for c in out[:2]),tuple(round(8+2*v/100,2) for v in w))
    def test_gap_soft_curve_zero_width_and_reverse(self):
        c=crossover_defaults();c['mode']='gap'
        self.assertEqual(crossover_weights(.5,c),(0,0))
        self.assertEqual(crossover_weights(.3,c),(1,0));self.assertEqual(crossover_weights(.7,c),(0,1))
        c.update(mode='blend',curve='smooth')
        self.assertAlmostEqual(crossover_weights(.45,c)[1],.15625)
        c['width']=0;self.assertEqual(crossover_weights(.49,c),(1,0));self.assertEqual(crossover_weights(.5,c),(0,1))
        data=self.settings();data['crossover']['invert']=True;self.apply(data)
        self.assertEqual(self.sample(.2)[0]['power'],0);self.assertEqual(self.sample(.8)[0]['power'],10)
    def test_channel_three_independent_axis_and_envelope(self):
        d=self.settings();d['channels'][2].update(axis='L1',power_mode='position')
        self.apply(d);self.e.ingest('L02000 L17500','test');out=self.e.snapshot()['channels']
        self.assertEqual([c['power'] for c in out],[10,0,7.5])
    def test_missing_shared_axis_does_not_mute_independent_channel(self):
        d=self.settings();d['channels'][2]['axis']='L1';self.apply(d)
        self.e.ingest('L17500','test');out=self.e.snapshot()['channels']
        self.assertEqual([c['power'] for c in out],[0,0,10])
    def test_unpaired_position_inversion_ranges(self):
        d=self.settings(False);a,b,c=d['channels'];a['power_mode']='position';b.update(power_mode='position',invert=True)
        c.update(axis='L1',power_mode='position',frequency_mode='position',frequency_min=40,frequency_max=120,width_mode='position',width_min=50,width_max=150)
        self.apply(d);self.e.ingest('L02500 L17500','test');a,b,c=self.e.snapshot()['channels']
        self.assertEqual([a['power'],b['power'],c['power']],[2.5,7.5,7.5]);self.assertEqual([c['frequency'],c['width']],[100,125])
    def test_interval_position_speed_and_expiry(self):
        d=self.settings(False);d['channels'][0].update(power_mode='position',frequency_mode='speed',frequency_min=40,frequency_max=100,width_mode='inverse_speed',width_min=80,width_max=120)
        self.apply(d);self.e.ingest('L00000','test');self.e.ingest('L09000I1000','test');self.clock.now+=.5
        c=self.e.snapshot()['channels'][0];self.assertEqual(c['power'],4.5);self.assertEqual(c['speed'],90);self.assertEqual(c['frequency'],94);self.assertEqual(c['width'],84)
        self.clock.now+=.6;c=self.e.snapshot()['channels'][0];self.assertEqual(c['power'],9);self.assertEqual(c['frequency'],40)
        self.clock.now+=2;c=self.e.snapshot()['channels'][0];self.assertEqual(c['power'],0)
    def test_velocity_reference_and_decay(self):
        d=self.settings(False);d['channels'][0].update(power_mode='speed',speed_reference=200)
        self.apply(d);self.e.ingest('L00000','test');self.clock.now+=.5;self.e.ingest('L05000','test')
        self.assertEqual(self.e.snapshot()['channels'][0]['power'],5)
        self.clock.now+=.3;p=self.e.snapshot()['channels'][0]['power'];self.assertGreater(p,1);self.assertLess(p,2)
    def test_power_rest_return_ramp_and_texture_rest_ranges(self):
        d=self.settings(False);c=d['channels'][0]
        c.update(power_min=8,power_max=10,power_rest_enabled=True,power_rest=40,power_ramp_s=1,
            frequency_mode='fixed',frequency_rest_enabled=True,frequency_rest=0,frequency_ramp_s=1)
        self.apply(d);self.e.ingest('L00000','test');out=self.e.snapshot()['channels'][0]
        self.assertEqual(out['power'],8.8);self.assertEqual(out['frequency'],40)
        self.e.ingest('L09000I1000','test');out=self.e.snapshot()['channels'][0];self.assertEqual(out['power'],8.8)
        self.clock.now+=.5;out=self.e.snapshot()['channels'][0]
        self.assertEqual(out['power'],9.4);self.assertEqual(out['frequency'],70)
        self.clock.now+=.6;self.assertEqual(self.e.snapshot()['channels'][0]['power'],8.8)
    def test_blend_and_output_limits(self):
        d=self.settings(False);c=d['channels'][0];c.update(power_mode='blend',power_speed_mix=25,frequency_mode='speed',width_mode='inverse_speed')
        self.apply(d);self.e.ingest('L00000','test');self.e.ingest('L08000I1000','test');self.clock.now+=.5
        c=self.e.snapshot()['channels'][0];self.assertEqual(c['power'],5)
        for x in (0,.1,.5,.9999):
            for c in self.sample(x):
                self.assertTrue(0<=c['power']<=10);self.assertTrue(40<=c['frequency']<=100);self.assertTrue(80<=c['width']<=120)
    def test_stale_neutral_and_disabled_are_immediate(self):
        self.apply();self.sample(.2);self.e.action('neutral')
        self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
        self.e.action('resume');self.assertEqual(self.e.snapshot()['channels'][0]['power'],10)
        self.clock.now+=2.1;self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
        d=self.settings();d['channels'][0]['enabled']=False;self.apply(d);self.assertEqual(self.sample(.2)[0]['power'],0)
    def test_smoothing_shared_and_neutral(self):
        d=self.settings();d['crossover']['smoothing_ms']=500;self.apply(d);self.sample(.2)
        self.clock.now+=.1;c=self.sample(.8);self.assertLess(c[0]['position'],.8)
        self.assertEqual(c[0]['position'],c[1]['position']);self.assertAlmostEqual(c[0]['weight']+c[1]['weight'],100)
        self.e.action('neutral');self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
    def test_demo_preserves_neutral_and_clears_live_input(self):
        self.e.ingest('L09000','test');self.e.action('neutral');self.e.action('demo_on')
        self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
        self.e.action('resume');self.assertGreater(sum(c['power'] for c in self.e.snapshot()['channels']),0)
        self.e.action('demo_off');self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
    def test_invalid_config_is_atomic(self):
        before=copy.deepcopy(self.e.config)
        for change in [dict(power_min=12,power_max=2),dict(width_min=0),dict(smoothing_ms=float('nan')),dict(axis='XX'),dict(enabled=1),dict(power_mode='bad')]:
            d=self.settings();d['channels'][0].update(change)
            with self.assertRaises(ValueError):self.e.configure(d)
            self.assertEqual(self.e.config,before)
        d=self.settings();d['crossover'].update(centre=5,width=20)
        with self.assertRaises(ValueError):self.e.configure(d)
        self.assertEqual(self.e.config,before)
    def test_background_survives_gap_rest_but_not_stop(self):
        d=self.settings();d['crossover']['mode']='gap'
        for c in d['channels']:c.update(power_min=4,power_rest_enabled=True,power_rest=0)
        self.apply(d);out=self.sample(.5)
        self.assertEqual([c['power'] for c in out],[4,4,4])
        self.assertEqual(out[0]['state'],'BACKGROUND')
        self.e.action('neutral');self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
        self.e.action('resume');self.clock.now+=2.1;self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
    def test_texture_damping_does_not_shrink_crossover(self):
        d=self.settings();c=d['channels'][0];c.update(frequency_mode='position',frequency_damping_ms=500,width_mode='inv_position_speed',width_speed_mix=0,width_damping_ms=500)
        self.apply(d);self.sample(0);self.clock.now+=.1;out=self.sample(.9999)
        self.assertEqual(out[0]['position'],.9999);self.assertEqual(out[0]['weight'],0)
        self.assertGreater(out[0]['frequency'],40);self.assertLess(out[0]['frequency'],100)
        self.e.action('neutral');self.e.action('resume');self.assertEqual(self.e.snapshot()['channels'][0]['frequency'],40)
    def test_older_v2_settings_get_damping_defaults(self):
        d=self.settings()
        for c in d['channels']:
            for stem in ('power','frequency','width'):c.pop(stem+'_damping_ms')
        self.apply(d);self.assertEqual(self.e.config[0]['frequency_damping_ms'],500)
        self.assertEqual(self.e.config[0]['power_damping_ms'],0)
    def test_idle_connected_source_holds_and_closed_source_does_not(self):
        self.apply();self.e.link_open('one','WebSocket')
        self.e.ingest('L02000','WebSocket',source='one')
        self.clock.now+=3600;self.e.link_alive('one')
        out=self.e.snapshot()['channels'];self.assertEqual(out[0]['power'],10)
        self.assertEqual(out[0]['position'],.2);self.assertEqual(out[0]['speed'],0)
        self.e.link_close('one');self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
        self.e.link_open('two','WebSocket');self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
        self.e.ingest('L03000','WebSocket',source='two');self.assertEqual(self.e.snapshot()['channels'][0]['power'],10)
    def test_link_heartbeat_expiry_pauses_while_udp_still_expires(self):
        self.apply();self.e.link_open('one','WebSocket');self.e.ingest('L02000','WebSocket',source='one')
        self.clock.now+=9;self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
        self.e.ingest('L02000','UDP');self.clock.now+=2.1
        self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
    def test_two_second_buffer_aligns_position_and_texture(self):
        d=self.settings(False);d['volume']=dict(enabled=True,delay_s=2,ratio=20)
        d['channels'][0].update(power_mode='position',frequency_mode='position')
        self.apply(d);self.e.link_open('one','WebSocket');self.e.ingest('L00000','WebSocket','one')
        self.assertEqual(self.e.snapshot()['channels'][0]['power'],0)
        self.clock.now=100.1;self.e.ingest('L09000','WebSocket','one')
        self.clock.now=102.05;c=self.e.snapshot()['channels'][0]
        self.assertAlmostEqual(c['position'],.45,places=3);self.assertEqual(c['power'],4.5);self.assertEqual(c['frequency'],67)
        self.e.action('neutral');self.assertEqual(self.e.snapshot()['channels'][0]['power'],0)
    def test_vector_ratio_rest_and_return_ramp_above_floor(self):
        d=self.settings(False);d['volume']=dict(enabled=True,delay_s=2,ratio=20)
        d['channels'][0].update(power_mode='vector',power_min=2,power_max=10,power_rest_enabled=True,power_rest=40,power_ramp_s=.5)
        self.apply(d);self.e.link_open('one','WebSocket')
        for i in range(10):
            self.clock.now=100+i*.1;self.e.ingest('L0'+str(i*1000).zfill(4),'WebSocket','one')
        self.clock.now=102.3;self.assertEqual(self.e.snapshot()['channels'][0]['power'],5.2)
        self.clock.now=102.8;self.assertEqual(self.e.snapshot()['channels'][0]['power'],10)
        self.clock.now=104;self.assertEqual(self.e.snapshot()['channels'][0]['power'],5.2)
        self.e.link_close('one');self.assertEqual(self.e.snapshot()['channels'][0]['power'],0)
    def test_delay_change_buffers_and_new_source_cannot_replay_old_data(self):
        d=self.settings();self.apply(d);self.e.link_open('old','WebSocket');self.e.ingest('L02000','WebSocket','old')
        self.clock.now+=3;d['volume']=dict(enabled=True,delay_s=2,ratio=20);self.apply(d)
        self.assertEqual(self.e.snapshot()['channels'][0]['state'],'BUFFERING')
        self.clock.now+=2;self.e.link_alive('old');self.assertGreater(self.e.snapshot()['channels'][0]['power'],0)
        self.e.link_close('old');self.e.link_open('new','WebSocket');self.e.ingest('L03000','WebSocket','new')
        self.assertEqual(self.e.snapshot()['channels'][0]['power'],0)
        self.clock.now+=2;self.e.link_alive('new');self.assertGreater(self.e.snapshot()['channels'][0]['power'],0)
    def test_rolling_speed_windows_and_recent_peak(self):
        from lookahead import MotionBuffer
        b=MotionBuffer()
        for t,v,expected in [(0,10,1),(1,2,.6),(2,0,.4),(7,2,.1),(33,2,1)]:
            b.push('L0',dict(at=t,start=0,target=.5,interval_ms=0,speed=v,source='one'))
            self.assertAlmostEqual(b.sample('L0',t)[2],expected)
    def test_rolling_volume_does_not_drop_on_one_stationary_sample(self):
        from lookahead import MotionBuffer
        b=MotionBuffer()
        for t,speed in [(0,1),(.1,0),(.2,0)]:
            b.push('L0',dict(at=t,start=.5,target=.5,interval_ms=0,speed=speed,source='one'))
        self.assertTrue(b.sample('L0',.15)[3]);self.assertFalse(b.sample('L0',.6)[3])
    def test_lookahead_validation_and_persistence(self):
        before=copy.deepcopy(self.e.config);d=self.settings();d['volume']=dict(enabled=True,delay_s=8,ratio=20)
        with self.assertRaises(ValueError):self.e.configure(d)
        self.assertEqual(self.e.config,before)
    def test_settings_roundtrip(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            p=Path(folder)/'settings.json';e=Engine(p);d=self.settings();d['channels'][2]['axis']='L1';e.configure(d)
            restored=Engine(p);self.assertEqual(restored.config,d['channels']);self.assertEqual(restored.crossover,d['crossover']);self.assertEqual(restored.volume,e.volume)
            p.write_text('broken');self.assertTrue(Engine(p).listener_errors)

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
            self.assertIn(b'PREVIEW ONLY',page)
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
