"""Buffered motion analysis adapted from Vector 1A's rolling-speed approach."""
from collections import deque
import math

def volume_defaults():
    return dict(enabled=False,delay_s=2.0,ratio=20.0)

class MotionBuffer:
    def __init__(self):
        self.history={};self.velocity={};self.peaks={}
    def clear(self):
        self.history.clear();self.velocity.clear();self.peaks.clear()
    def push(self,axis,entry):
        now=entry['at'];history=self.history.setdefault(axis,deque(maxlen=12000))
        if history and history[-1].get('source')!=entry.get('source'):
            history.clear();self.velocity.pop(axis,None);self.peaks.pop(axis,None)
        velocities=self.velocity.setdefault(axis,deque(maxlen=12000))
        duration=entry['interval_ms']/1000
        speed=abs(entry['target']-entry['start'])/duration if duration>0 else entry['speed']
        velocities.append((now,speed))
        while velocities and velocities[0][0]<now-5:velocities.popleft()
        rolling=sum(v for _,v in velocities)/len(velocities)
        peaks=self.peaks.setdefault(axis,deque(maxlen=12000));peaks.append((now,rolling))
        while peaks and peaks[0][0]<now-30:peaks.popleft()
        peak=max(v for _,v in peaks)
        history.append(dict(entry,normalized=rolling/peak if peak>1e-9 else 0.))
        while len(history)>1 and history[1]['at']<now-45:history.popleft()
    def sample(self,axis,at):
        history=self.history.get(axis)
        if not history:return None
        left=right=None
        for e in reversed(history):
            if e['at']<=at:left=e;break
            right=e
        if left is None:return None
        duration=left['interval_ms']/1000
        age=max(0,at-left['at'])
        if duration>0:
            u=min(1,age/duration);x=left['start']+(left['target']-left['start'])*u
            speed=abs(left['target']-left['start'])/duration if age<duration else 0.
            moving=speed>.005 and age<duration
        elif right is not None and 0<right['at']-left['at']<=.25:
            gap=right['at']-left['at'];x=left['target']+(right['target']-left['target'])*age/gap
            speed=abs(right['target']-left['target'])/gap
            # Vector uses rolling speed plus input recency, not instantaneous velocity.
            moving=age<=.25 and left['normalized']>.005
        else:
            x=left['target'];speed=left['speed']*math.exp(-age/.3)
            moving=age<=.25 and left['normalized']>.005
        return x,speed,left['normalized'],moving
