import unittest,random,copy,json,tempfile
from pathlib import Path
from curves import evaluate,validate_curve,preset,PRESETS
from engine import Engine,defaults,crossover_defaults,migrate_settings
class Clock:
 def __init__(self):self.now=100.
 def __call__(self):return self.now
class CurveTests(unittest.TestCase):
 def test_knots_bounds_and_monotonic_segments(self):
  rng=random.Random(52)
  for _ in range(80):
   p=[[0,rng.uniform(0,100)]]+[[x,rng.uniform(0,100)] for x in sorted(rng.sample(range(1,100),8))]+[[100,rng.uniform(0,100)]]
   c=validate_curve(dict(points=p,interpolation='smooth'))
   for x,y in p:self.assertAlmostEqual(evaluate(c,x/100),y/100)
   for a,b in zip(p,p[1:]):
    vals=[evaluate(c,(a[0]+(b[0]-a[0])*j/50)/100) for j in range(51)]
    self.assertTrue(all(min(a[1],b[1])/100-1e-10<=v<=max(a[1],b[1])/100+1e-10 for v in vals))
    self.assertTrue(all((v-u)*(b[1]-a[1])>=-1e-10 for u,v in zip(vals,vals[1:])))
 def test_linear_crossover_and_flat(self):
  for x,y in [(0,1),(.4,1),(.45,.75),(.5,.5),(.6,0),(1,0)]:
   self.assertAlmostEqual(evaluate(preset('crossover_1','linear'),x),y)
   self.assertAlmostEqual(evaluate(preset('crossover_2','linear'),x),1-y)
  self.assertEqual(evaluate(preset('flat'),.4),1)
 def test_reject_bad_curves(self):
  for p in [[],[[0,0]],[[0,0],[0,1],[100,0]],[[1,0],[100,0]],[[0,-1],[100,0]],[[0,0],[100,float('nan')]],[[0,0],[.01,2],[100,0]]]:
   with self.assertRaises(ValueError):validate_curve(dict(points=p,interpolation='smooth'))
  with self.assertRaises(ValueError):validate_curve(dict(points=[[0,0],[100,1]],interpolation='spline'))
class FourChannelTests(unittest.TestCase):
 def setUp(self):
  self.clock=Clock();self.e=Engine(clock=self.clock);self.d=dict(channels=defaults(),crossover=crossover_defaults())
  for c in self.d['channels']:
   c.update(enabled=True,power_min=2,power_max=10,power_mode='fixed',power_rest_enabled=False,smoothing_ms=0,curve=preset('flat'))
 def sample(self):
  self.e.configure(self.d);self.e.ingest('L02500','test');return self.e.snapshot()['channels']
 def test_four_curves_background_and_off(self):
  for c,name in zip(self.d['channels'],['rising','falling','triangle','flat']):c['curve']=preset(name,'linear')
  out=self.sample();self.assertEqual([c['power'] for c in out],[4,8,6,10]);self.assertEqual(len(out),4)
  self.d['channels'][3]['enabled']=False;self.assertEqual(self.sample()[3]['power'],0)
  self.e.action('neutral');self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
 def test_independent_source_and_follow(self):
  self.d['channels'][3].update(axis='L1',frequency_follow_ab=True,width_follow_ab=True)
  self.d['channels'][0].update(frequency_mode='fixed',frequency_max=123,width_mode='fixed',width_max=151)
  out=self.sample();self.assertEqual(out[3]['power'],0)
  self.e.ingest('L17500','test');out=self.e.snapshot()['channels'];self.assertEqual(out[3]['power'],10);self.assertEqual((out[3]['frequency'],out[3]['width']),(123,151))
 def test_rest_and_curve_preserve_floor(self):
  c=self.d['channels'][0];c.update(power_rest_enabled=True,power_rest=0,curve=preset('rising'))
  self.assertEqual(self.sample()[0]['power'],2)
  self.clock.now+=3;self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
 def test_idle_link_loss_and_buffer(self):
  self.e.configure(self.d);self.e.link_open('one','WebSocket');self.e.ingest('L02500','WebSocket','one')
  self.clock.now+=100;self.e.link_alive('one');self.assertEqual(self.e.snapshot()['channels'][3]['power'],10)
  self.e.link_close('one');self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']))
  self.d['volume']=dict(enabled=True,delay_s=2,ratio=20);self.e.configure(self.d);self.e.link_open('two','WebSocket');self.e.ingest('L05000','WebSocket','two')
  self.assertTrue(all(c['power']==0 for c in self.e.snapshot()['channels']));self.clock.now+=2;self.e.link_alive('two');self.assertEqual(self.e.snapshot()['channels'][3]['power'],10)
 def test_config_atomic_and_persistence(self):
  self.sample();old=copy.deepcopy(self.e.config);bad=copy.deepcopy(self.d);bad['channels'][3]['curve']['points'][0][1]=101
  with self.assertRaises(ValueError):self.e.configure(bad)
  self.assertEqual(self.e.config,old)
  with tempfile.TemporaryDirectory(dir=Path.cwd()) as t:
   path=Path(t)/'settings.json';e=Engine(path);e.configure(self.d);self.assertEqual(Engine(path).config,e.config)
 def test_migrate_three_channel_settings(self):
  d=copy.deepcopy(self.d);d['channels']=d['channels'][:3];d['crossover']['enabled']=True
  for c in d['channels']:c.pop('curve')
  migrated=migrate_settings(d);self.assertEqual(len(migrated['channels']),4);self.assertFalse(migrated['channels'][3]['enabled'])
  self.assertEqual(evaluate(migrated['channels'][0]['curve'],.5),.5)
  self.assertEqual(d['channels'][0].get('curve'),None)

class GlobalInvertTests(FourChannelTests):
 def test_input_invert_before_curves_and_individual_invert(self):
  for c in self.d['channels']:c['curve']=preset('rising','linear')
  self.d['input_invert']=True;self.d['channels'][1]['invert']=True
  rows=self.sample();self.assertEqual([c['power'] for c in rows],[8,4,8,8])
  state=self.e.snapshot();self.assertEqual(state['axes']['L0']['raw_value'],.25);self.assertEqual(state['axes']['L0']['value'],.75)
  self.assertEqual(state['last_packet'],'L02500')
 def test_input_invert_persistence_and_type(self):
  self.d['input_invert']=True
  with tempfile.TemporaryDirectory(dir=Path.cwd()) as t:
   p=Path(t)/'settings.json';e=Engine(p);e.configure(self.d);self.assertTrue(Engine(p).input_invert)
  self.d['input_invert']='yes'
  with self.assertRaises(ValueError):self.e.configure(self.d)
 def test_buffered_global_invert_does_not_rewrite_input_history(self):
  self.d.update(input_invert=True,volume=dict(enabled=True,delay_s=2,ratio=20))
  self.d['channels'][0]['curve']=preset('rising','linear')
  self.e.configure(self.d);self.e.link_open('one','WebSocket');self.e.ingest('L02500','WebSocket','one')
  self.clock.now+=2;self.e.link_alive('one')
  self.assertEqual(self.e.snapshot()['channels'][0]['power'],8)
  self.d['input_invert']=False;self.e.configure(self.d)
  self.assertEqual(self.e.snapshot()['channels'][0]['power'],4)

class InputTransportTests(unittest.TestCase):
 def test_udp_only_filters_websocket_and_switch_clears_history(self):
  e=Engine();d=dict(channels=defaults(),crossover=crossover_defaults(),input_transport='UDP');e.configure(d)
  e.ingest('L02500','WebSocket');self.assertEqual(e.count,0)
  e.ingest('L07500','UDP');self.assertEqual(e.count,1);self.assertAlmostEqual(e.snapshot()['axes']['L0']['value'],.75)
  d['input_transport']='WebSocket';e.configure(d);self.assertFalse(e.snapshot()['axes']);e.ingest('L00000','UDP');self.assertEqual(e.count,1)
  d['input_transport']='bad'
  with self.assertRaises(ValueError):e.configure(d)
