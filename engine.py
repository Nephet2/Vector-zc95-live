"""Deterministic ZC95 command preview; no Bluetooth/device side effects."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import threading
import time
from lookahead import MotionBuffer, volume_defaults
from curves import preset, evaluate, validate_curve

AXES = [f'{a}{i}' for a in 'LRVAPEBC' for i in range(10)]
MODES = ('fixed', 'position', 'speed', 'inverse_speed', 'blend', 'inv_position_speed', 'vector')

def crossover_defaults():
    return dict(enabled=False, axis='L0', invert=False, centre=50, width=20,
                mode='blend', curve='linear', smoothing_ms=0, speed_reference=100)

def defaults():
    rows = []
    for i, name in enumerate(('Channel 1', 'Channel 2', 'Channel 3', 'Channel 4')):
        c = dict(name=name, axis='L0', invert=False, enabled=i<2,
                 power_min=0, power_max=10, frequency_min=40, frequency_max=100,
                 width_min=80, width_max=120, smoothing_ms=0, speed_reference=100)
        c.update(frequency_follow_ab=False, width_follow_ab=False, curve=preset('crossover_'+str(i+1) if i<2 else 'flat', 'linear' if i<2 else 'smooth'))
        for stem, mode in [('power', 'fixed'),
                           ('frequency', 'blend'), ('width', 'inv_position_speed')]:
            c.update({stem+'_mode':mode, stem+'_speed_mix':67 if stem!='power' else 50, stem+'_damping_ms':500 if stem!='power' else 0,
                      stem+'_rest_enabled':stem == 'power' and i < 2,
                      stem+'_rest':40 if stem == 'power' else 100,
                      stem+'_ramp_s':.5})
        rows.append(c)
    return rows

def numeric(data, key, lo, hi):
    n = data.get(key)
    if type(n) not in (float, int) or not math.isfinite(n) or not lo <= n <= hi:
        raise ValueError(f'{key} must be {lo}–{hi}')
    return n

def boolean(data, key):
    if type(data.get(key)) is not bool: raise ValueError('Invalid toggle: '+key)
    return data[key]

def validate_cross(data):
    if not isinstance(data, dict): raise ValueError('Invalid crossover settings')
    c = crossover_defaults()
    for k in ('enabled', 'invert'): c[k] = boolean(data, k)
    if data.get('axis') not in AXES: raise ValueError('Invalid crossover source axis')
    c['axis'] = data['axis']
    for k, lo, hi in [('centre',0,100),('width',0,100),('smoothing_ms',0,2000),('speed_reference',10,500)]:
        c[k] = numeric(data,k,lo,hi)
    if c['centre']-c['width']/2 < 0 or c['centre']+c['width']/2 > 100:
        raise ValueError('Crossover band must fit within 0–100%')
    if data.get('mode') not in ('blend','gap'): raise ValueError('Invalid crossover mode')
    if data.get('curve') not in ('linear','smooth'): raise ValueError('Invalid crossover curve')
    c['mode'], c['curve'] = data['mode'], data['curve']
    return c

def validate(rows):
    if not isinstance(rows,list) or len(rows)!=4: raise ValueError('Exactly four channel mappings are required')
    result = defaults()
    for src, c in zip(rows,result):
        if not isinstance(src,dict) or src.get('axis') not in AXES: raise ValueError('Invalid source axis')
        c['axis'] = src['axis']
        c['curve'] = validate_curve(src.get('curve',c['curve']))
        for k in ('invert','enabled'): c[k] = boolean(src,k)
        for k in ('frequency_follow_ab','width_follow_ab'):
            c[k] = boolean({k:False,**src},k) if c['name']!='Channel 1' else False
        for stem,lo,hi in [('power',0,100),('frequency',1,255),('width',1,255)]:
            for end in ('min','max'): c[stem+'_'+end] = numeric(src,stem+'_'+end,lo,hi)
            if c[stem+'_min']>c[stem+'_max']: raise ValueError(stem+' minimum exceeds maximum')
            if src.get(stem+'_mode') not in MODES: raise ValueError('Invalid '+stem+' response')
            c[stem+'_mode'] = src[stem+'_mode']
            c[stem+'_speed_mix'] = numeric(src,stem+'_speed_mix',0,100)
            # Older v2 settings gain independent texture damping without losing ranges.
            c[stem+'_damping_ms'] = numeric({**{stem+'_damping_ms':c[stem+'_damping_ms']},**src},stem+'_damping_ms',0,5000)
            c[stem+'_rest_enabled'] = boolean(src,stem+'_rest_enabled')
            c[stem+'_rest'] = numeric(src,stem+'_rest',0,100)
            c[stem+'_ramp_s'] = numeric(src,stem+'_ramp_s',0,10)
        for k,lo,hi in [('smoothing_ms',0,2000),('speed_reference',10,500)]: c[k]=numeric(src,k,lo,hi)
    return result

def migrate_settings(data):
    import copy
    data=copy.deepcopy(data)
    if not isinstance(data,dict):raise ValueError('Invalid settings')
    rows=data.get('channels')
    if isinstance(rows,list) and len(rows)==3:
        cross=validate_cross(data['crossover'])
        for i,c in enumerate(rows):
            c['name']='Channel '+str(i+1)
            if i<2 and cross['enabled']:
                for key in ('axis','invert','smoothing_ms','speed_reference'):c[key]=cross[key]
                if cross['width']==0 or cross['mode']=='gap':
                    raise ValueError('Legacy gap/zero-width settings need manual curve setup')
                lo=cross['centre']-cross['width']/2;hi=cross['centre']+cross['width']/2
                pts=[[0,100],[lo,100],[hi,0],[100,0]]
                pts=[p for j,p in enumerate(pts) if j==0 or p[0]!=pts[j-1][0]]
                if i==1:pts=[[x,100-y] for x,y in pts]
                c['curve']=dict(points=pts,interpolation='linear' if cross['curve']=='linear' else 'smooth')
            else:c['curve']=preset('flat')
        rows.append(defaults()[3])
    data['crossover']={**crossover_defaults(),'enabled':False}
    return data

def crossover_weights(position, c):
    """Position is already direction-adjusted. Weights are command shares."""
    x = max(0,min(100,position*100));lo=c['centre']-c['width']/2;hi=c['centre']+c['width']/2
    if hi==lo: return (1.,0.) if x<lo else (0.,1.)
    if c['mode']=='gap': return (float(x<=lo),float(x>=hi))
    t=max(0,min(1,(x-lo)/(hi-lo)))
    if c['curve']=='smooth': t=t*t*(3-2*t)
    return 1-t,t

def axis_value(entry,now):
    duration=entry['interval_ms']/1000
    t=1 if duration<=0 else max(0,min(1,(now-entry['at'])/duration))
    return entry['start']+(entry['target']-entry['start'])*t

def axis_speed(entry,now):
    duration=entry['interval_ms']/1000
    if duration>0:
        return abs(entry['target']-entry['start'])/duration if now<entry['at']+duration else 0.
    return entry['speed']*math.exp(-max(0,now-entry['at'])/.3)

class Engine:
    def __init__(self,settings=None,clock=time.monotonic):
        self.settings=settings;self.clock=clock;self.lock=threading.RLock()
        self.config=defaults();self.crossover=crossover_defaults();self.input_invert=False;self.input_transport='auto';self.axes={};self.links={}
        self.motion=MotionBuffer();self.volume=volume_defaults();self.buffer_started=clock()
        self.count=0;self.last_packet='';self.transport='None';self.neutral=False;self.demo=False
        self.started=clock();self.previous_tick=clock();self.smooth={};self.attacks={};self.responses={};self.listener_errors=[]
        initial_settings = settings if settings and settings.exists() else (settings.with_name('starter-settings.json') if settings else None)
        if initial_settings and initial_settings.exists():
            try:
                data=json.loads(initial_settings.read_text(encoding='utf-8-sig'))
                data=migrate_settings(data)
                rows=validate(data['channels']);cross=validate_cross(data['crossover'])
                volume=self.validate_volume(data.get('volume',volume_defaults()))
                self.config=rows;self.crossover=cross;self.volume=volume
                self.input_invert=boolean({'input_invert':False,**data},'input_invert')
                self.input_transport=self.validate_input_transport(data.get('input_transport','auto'))
            except (ValueError,KeyError,TypeError,OSError) as e:self.listener_errors.append('Settings ignored: '+str(e))

    def link_open(self,key,transport):
        with self.lock:self.links[key]=dict(transport=transport,seen=self.clock())
    def link_alive(self,key):
        with self.lock:
            if key in self.links:self.links[key]['seen']=self.clock()
    def link_close(self,key):
        with self.lock:self.links.pop(key,None)
    def fresh(self,entry,now):
        if not entry:return False
        source=entry.get('source')
        if source is not None:
            link=self.links.get(source)
            return bool(link and now-link['seen']<=8)
        return now-entry['at']<=2+entry['interval_ms']/1000

    def ingest(self,message,transport,source=None):
        from tcode import parse_message
        if self.input_transport!='auto' and transport!=self.input_transport:return
        commands=parse_message(message[:65536]);now=self.clock()
        with self.lock:
            for cmd in commands:
                if cmd.axis not in AXES:continue
                old=self.axes.get(cmd.axis)
                fresh=self.fresh(old,now)
                start=axis_value(old,now) if fresh else cmd.value
                elapsed=now-old['at'] if fresh else 0
                # Interval timing is used directly; immediate commands use arrival velocity.
                speed=abs(cmd.value-old['target'])/elapsed if elapsed>1e-4 else (old['speed'] if fresh else 0.)
                self.axes[cmd.axis]=dict(start=start,target=cmd.value,at=now,
                    interval_ms=min(cmd.interval_ms,30000),speed=min(speed,20.),source=source)
                self.motion.push(cmd.axis,self.axes[cmd.axis])
                self.count+=1
            if commands:self.last_packet=message[:240];self.transport=transport

    @staticmethod
    def validate_volume(data):
        if not isinstance(data,dict):raise ValueError('Invalid look-ahead settings')
        return dict(enabled=boolean(data,'enabled'),delay_s=numeric(data,'delay_s',0,5),ratio=numeric(data,'ratio',10,40))
    @staticmethod
    def validate_input_transport(value):
        if value not in ('auto','UDP','WebSocket','TCP'):raise ValueError('Invalid input transport')
        return value
    def configure(self,data):
        if not isinstance(data,dict):raise ValueError('Settings require channels and crossover')
        input_transport=self.validate_input_transport(data.get('input_transport',self.input_transport))
        input_invert=boolean({'input_invert':self.input_invert,**data},'input_invert')
        rows=validate(data.get('channels'));cross=validate_cross(data.get('crossover'));volume=self.validate_volume(data.get('volume',self.volume))
        with self.lock:
            if self.settings:
                temp=self.settings.with_suffix('.tmp')
                temp.write_text(json.dumps(dict(channels=rows,crossover=cross,volume=volume,input_invert=input_invert,input_transport=input_transport),indent=2),encoding='utf-8')
                os.replace(temp,self.settings)
            if self.input_transport!=input_transport:
                self.axes={};self.motion.clear();self.buffer_started=self.clock();self.smooth={};self.attacks={};self.responses={}
            self.input_transport=input_transport
            changed = self.input_invert!=input_invert or any(a[k]!=b[k] for a,b in zip(self.config,rows) for k in ('axis','invert')) or any(self.crossover[k]!=cross[k] for k in ('enabled','axis','invert'))
            if (self.volume['enabled'],self.volume['delay_s'])!=(volume['enabled'],volume['delay_s']):
                self.buffer_started=self.clock();changed=True
            self.config=rows;self.crossover=cross;self.volume=volume;self.input_invert=input_invert
            if changed:self.smooth={};self.attacks={};self.responses={}

    def action(self,action):
        with self.lock:
            if action=='neutral':self.neutral=True
            elif action=='resume':self.neutral=False
            elif action in ('demo_on','demo_off'):
                self.demo=action=='demo_on';self.started=self.clock();self.axes={};self.motion.clear()
            else:raise ValueError('Unknown action')
            self.buffer_started=self.clock()
            self.smooth={};self.attacks={};self.responses={}

    def source(self,axis,invert,reference,now):
        entry=self.axes.get(axis);fresh=self.fresh(entry,now)
        delay=self.volume['delay_s'] if self.volume['enabled'] else 0.
        at=now-delay;vector_speed=0.;vector_moving=False
        if self.demo:
            phase=(at-self.started)*math.pi/2
            x=(math.sin(phase)+1)/2;velocity=abs(math.cos(phase)*math.pi/4)
            vector_speed=min(1,velocity/(math.pi/4));vector_moving=velocity>.005;fresh=True
        elif delay>0:
            sample=self.motion.sample(axis,at)
            if sample is None:x=velocity=0.;fresh=False
            else:x,velocity,vector_speed,vector_moving=sample
        else:
            x=axis_value(entry,now) if entry else 0;velocity=axis_speed(entry,now) if entry and fresh else 0
            sample=self.motion.sample(axis,now)
            if sample is not None:_,_,vector_speed,vector_moving=sample
        if delay>0 and now-self.buffer_started<delay:fresh=False
        return (1-x if invert != self.input_invert else x),min(1,velocity/(reference/100)),velocity>.005,fresh,vector_speed,vector_moving

    def smooth_position(self,key,x,ms,dt,fresh):
        if not fresh:self.smooth.pop(key,None);return x
        prev=self.smooth.get(key)
        a=1 if ms==0 else 1-math.exp(-dt/(ms/1000))
        value=x if prev is None else prev+(x-prev)*a
        self.smooth[key]=value;return value

    def parameter(self,c,stem,x,speed,moving,now,i,dt,vector_speed=0.,vector_moving=False):
        mode=c[stem+'_mode'];mix=c[stem+'_speed_mix']/100
        if mode=='vector':moving=vector_moving
        drive={'fixed':1.,'position':x,'speed':speed,'inverse_speed':1-speed,'blend':x*(1-mix)+speed*mix,'inv_position_speed':(1-x)*(1-mix)+speed*mix,'vector':(self.volume['ratio']-1+vector_speed)/self.volume['ratio']}[mode]
        factor=1.
        key=(i,stem)
        if c[stem+'_rest_enabled']:
            rest=c[stem+'_rest']/100
            if not moving:self.attacks.pop(key,None);factor=rest
            else:
                started=self.attacks.setdefault(key,now);ramp=c[stem+'_ramp_s']
                progress=1. if ramp==0 else min(1,(now-started)/ramp)
                factor=rest+(1-rest)*progress
        lo,hi=c[stem+'_min'],c[stem+'_max']
        # Modulate only the excursion above minimum; power minimum is the background.
        target=max(0,min(1,drive*factor))
        damping=c[stem+'_damping_ms']
        previous=self.responses.get(key,0.)
        alpha=1. if damping==0 or mode=='fixed' else 1-math.exp(-dt/(damping/1000))
        response=previous+(target-previous)*alpha
        self.responses[key]=response
        return lo+(hi-lo)*response

    def snapshot(self):
        now=self.clock()
        with self.lock:
            dt=min(.5,max(0,now-self.previous_tick));self.previous_tick=now
            incoming={k:dict(raw_value=axis_value(v,now),value=1-axis_value(v,now) if self.input_invert else axis_value(v,now),age=round(now-v['at'],2),interval_ms=v['interval_ms']) for k,v in self.axes.items()}
            cross=self.crossover
            cx,cs,cm,cf,cvs,cvm=self.source(cross['axis'],cross['invert'],cross['speed_reference'],now)
            cx=self.smooth_position('cross',cx,cross['smoothing_ms'],dt,cf and not self.neutral)
            weights=crossover_weights(cx,cross)
            channels=[]
            for i,c in enumerate(self.config):
                paired=False
                x,speed,moving,fresh,vs,vm=(cx,cs,cm,cf,cvs,cvm) if paired else self.source(c['axis'],c['invert'],c['speed_reference'],now)
                if not paired:x=self.smooth_position(i,x,c['smoothing_ms'],dt,fresh and not self.neutral and c['enabled'])
                weight=evaluate(c['curve'],x)
                active=fresh and c['enabled'] and not self.neutral
                if active:
                    envelope=self.parameter(c,'power',x,speed,moving,now,i,dt,vs,vm)
                    p=c['power_min']+(envelope-c['power_min'])*weight
                    f=channels[0]['frequency'] if i>0 and c['frequency_follow_ab'] else self.parameter(c,'frequency',x,speed,moving,now,i,dt)
                    w=channels[0]['width'] if i>0 and c['width_follow_ab'] else self.parameter(c,'width',x,speed,moving,now,i,dt)
                else:
                    for stem in ('power','frequency','width'):
                        self.attacks.pop((i,stem),None);self.responses.pop((i,stem),None)
                    envelope=0
                    p,f,w=0,c['frequency_min'],c['width_min']
                status='NEUTRAL' if self.neutral else ('DISABLED' if not c['enabled'] else (('BACKGROUND' if c['power_min']>0 else 'GATED OFF') if active and weight==0 else ('PREVIEW' if active else ('BUFFERING' if self.volume['enabled'] and self.fresh(self.axes.get(cross['axis'] if paired else c['axis']),now) else 'STALE / NO INPUT'))))
                channels.append(dict(channel=i+1,name=c['name'],axis=cross['axis'] if paired else c['axis'],state=status,
                    position=round(x,4),vector_speed=round(vs*100,1),speed=round(speed*100,1),weight=round(weight*100,2),
                    envelope=round(envelope,2),background=c['power_min'] if active else 0,power=round(max(0,min(100,p)),2),frequency=round(f),width=round(w)))
            return dict(version='0.9.2-wifi',mode='DEMO' if self.demo else 'MFP LIVE',neutral=self.neutral,
                config=self.config,input_transport=self.input_transport,input_invert=self.input_invert,volume=self.volume,buffer_remaining=round(max(0,self.volume['delay_s']-(now-self.buffer_started)),2) if self.volume['enabled'] else 0,crossover=cross,crossover_position=round(cx*100,2),
                defaults=dict(channels=defaults(),crossover=crossover_defaults(),volume=volume_defaults(),input_invert=False),axes=incoming,channels=channels,
                input_links=sum(1 for link in self.links.values() if self.input_transport=='auto' or link['transport']==self.input_transport),count=self.count,last_packet=self.last_packet,transport=self.transport,errors=self.listener_errors,hardware_output=False)
