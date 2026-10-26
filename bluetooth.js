/* ZC95 general-control BLE backend. One serialized writer; no pulse streaming. */
'use strict';
class ZC95Output {
  constructor(report=()=>{}) {
    this.report=report;this.device=null;this.channels=[];this.ready=false;this.armed=false;this.requested=false;this.suspended=false;this.nextRetryAt=0;
    this.connecting=false;this.epoch=0;this.latest=null;this.pumping=null;
    this.stopping=null;this.subscriptions=[];this.lastFrameAt=0;this.dials=[null,null,null,null];
    this.sent=[0,0,0,0];this.cache=new Map();this.clock=()=>performance.now();
    this.watchdog=setInterval(()=>this.maintain(),100);
  }
  maintain(){
    if(this.armed&&this.clock()-this.lastFrameAt>800)void this.pause('Command feed stalled; waiting to resume');
    if(this.requested&&!this.suspended&&!this.ready&&!this.connecting&&this.device&&this.clock()-this.lastFrameAt<800&&this.clock()>=this.nextRetryAt){this.nextRetryAt=this.clock()+5000;void this.connect(true);}
  }
  pause(reason){return this.stop(reason,true);}
  uuid(s){return 'ac7744c0-0bad-11ef-a9cd-0800200c9'+s;}
  notify(message){this.message=message;this.report({message,connected:this.ready,connecting:this.connecting,armed:this.armed,requested:this.requested,
    sent:[...this.sent],dials:[...this.dials],firmware:this.firmware||'—',battery:this.battery??'—'});}
  async deadline(p,label,ms=1500){let t;const device=this.device;try{return await Promise.race([p,new Promise((_,reject)=>{
    t=setTimeout(()=>{device?.gatt.disconnect();reject(Error(label+' timed out; disconnected'));},ms);
  })]);}finally{clearTimeout(t);}}
  valid(ticket){if(ticket!==this.epoch||!this.device?.gatt.connected)throw Error('Operation cancelled or Bluetooth disconnected');}
  async write(c,bytes,ticket=null){if(ticket!==null)this.valid(ticket);if(!this.device?.gatt.connected)throw Error('Bluetooth disconnected');
    await this.deadline(c.writeValueWithoutResponse(new Uint8Array(bytes)),'Channel write',this.connecting?10000:1500);
    if(ticket!==null)this.valid(ticket);
  }
  async offAll(){const failures=[];for(const c of this.channels)try{await this.write(c.enable,[0]);}catch(e){failures.push(e.message);}
    for(const c of this.channels)if(c.power)try{await this.write(c.power,[0,0]);}catch(e){failures.push(e.message);}
    if(failures.length)throw Error(failures.join('; '));this.sent=[0,0,0,0];this.cache.clear();
  }
  async watch(c,fn){fn(await this.deadline(c.readValue(),'Read',20000));const f=e=>fn(e.target.value);
    c.addEventListener('characteristicvaluechanged',f);this.subscriptions.push([c,f]);await this.deadline(c.startNotifications(),'Subscribe',20000);}
  cleanup(){this.epoch++;this.ready=false;this.armed=false;this.latest=null;this.channels=[];this.sent=[null,null,null,null];
    this.cache.clear();for(const[c,f]of this.subscriptions)c.removeEventListener('characteristicvaluechanged',f);this.subscriptions=[];}
  disconnect(message='Disconnected; output state not measured',manual=true){if(manual)this.requested=false;this.device?.gatt.disconnect();this.cleanup();this.notify(message);}
  async connect(reuse=false){if(this.connecting||this.device?.gatt.connected)return;this.connecting=true;this.notify(reuse?'Reconnecting ZC95':'Select ZC95');
    try{if(!navigator.bluetooth)throw Error('Use Chrome or Edge on this Windows PC');
      if(!reuse||!this.device)this.device=await navigator.bluetooth.requestDevice({filters:[{services:[this.uuid('b00')]},{namePrefix:'ZC95'}],optionalServices:[this.uuid('b00'),'device_information','battery_service']});
      const device=this.device,ticket=++this.epoch;this.dials=[null,null,null,null];
      device.ongattserverdisconnected=()=>{if(device!==this.device)return;if(this.connecting){this.notify('Link dropped during setup; retrying');return;}this.cleanup();this.nextRetryAt=this.clock()+1000;this.notify(this.requested?'Bluetooth lost; waiting to reconnect':'Bluetooth disconnected');};
      let g,s;
      for(let attempt=1;attempt<=3;attempt++){try{this.notify('Connection attempt '+attempt+' / 3');
        g=await this.deadline(device.gatt.connect(),'Connect',30000);await new Promise(r=>setTimeout(r,400));this.valid(ticket);
        s=await this.deadline(g.getPrimaryService(this.uuid('b00')),'Service discovery',30000);this.valid(ticket);break;
      }catch(e){if(ticket!==this.epoch)throw e;device.gatt.disconnect();if(attempt===3)throw e;await new Promise(r=>setTimeout(r,1200));}}
      this.channels=[];
      for(let i=1;i<=4;i++){this.valid(ticket);this.channels.push({enable:await this.deadline(s.getCharacteristic(this.uuid('b4'+i)),'Enable discovery',20000)});}
      await this.offAll();
      for(let i=1;i<=4;i++)for(const[key,suffix]of [['power','b3'],['width','b1'],['frequency','b2']]){
        this.valid(ticket);this.channels[i-1][key]=await this.deadline(s.getCharacteristic(this.uuid(suffix+i)),'Parameter discovery',20000);}
      await this.offAll();
      for(let i=1;i<=4;i++)await this.watch(await this.deadline(s.getCharacteristic(this.uuid('b0'+i)),'Dial discovery',20000),v=>{
        if(v.byteLength!==2)throw Error('Invalid dial payload');const n=v.getUint16(0,true);if(n>1000)throw Error('Invalid dial value');this.dials[i-1]=n/10;this.notify('Dial feedback updated');});
      try{const d=await this.deadline(g.getPrimaryService('device_information'),'Device info',20000);
        this.firmware=new TextDecoder().decode(await this.deadline((await d.getCharacteristic('firmware_revision_string')).readValue(),'Firmware',20000));}catch(e){this.firmware='unavailable';}
      try{const b=await g.getPrimaryService('battery_service');await this.watch(await b.getCharacteristic('battery_level'),v=>{this.battery=v.getUint8(0);});}catch(e){this.battery='unavailable';}
      this.valid(ticket);this.ready=true;this.notify('Connected. All OFF and zero-power commands sent.');
    }catch(e){this.disconnect('Connect failed: '+e.message,false);this.nextRetryAt=this.clock()+5000;}finally{this.connecting=false;this.notify(this.ready?'Connected / output stopped':this.message||'Disconnected');}
  }
  check(frame){if(!frame||frame.version!=='0.9.2-wifi')throw Error('Restart the v0.9.2 launcher; backend version differs');
    if(!Array.isArray(frame.config)||frame.config.length!==4||!Array.isArray(frame.channels)||frame.channels.length!==4||frame.channels.some((c,i)=>!c||c.channel!==i+1)||frame.config.some(c=>!c||typeof c.enabled!=='boolean'))throw Error('Invalid four-channel frame');
    if(frame.neutral)throw Error('Hard Neutral is active');
    const active=frame.channels.filter((_,i)=>frame.config[i].enabled);
    if(!active.length)throw Error('Enable a channel first');
    for(const c of active){if(!['PREVIEW','GATED OFF','BACKGROUND'].includes(c.state))throw Object.assign(Error('Waiting for live input on enabled channels'),{waiting:true});
      if(!Number.isFinite(c.power)||c.power<0||c.power>100||!Number.isFinite(c.frequency)||c.frequency<1||c.frequency>255||!Number.isFinite(c.width)||c.width<1||c.width>255)throw Error('Invalid command frame');}
  }
  arm(frame,scale){if(!this.ready||this.connecting||this.stopping||this.pumping)throw Error('Wait for Bluetooth setup / stop to finish');
    if(!scale)throw Error('Select Scale power-dial mode on the ZC95 and tick its checkbox');
    if(this.suspended)throw Error('Output is paused while the tab is hidden');this.check(frame);this.requested=true;this.armedAt=this.clock();this.armed=true;this.cache.clear();this.epoch++;
    this.notify('Continuous output active; configured power range');this.update(frame);
  }
  update(frame){
    this.lastFrameAt=this.clock();
    if(!this.requested)return;
    if(this.suspended){if(this.armed)void this.pause('Tab hidden; output paused');return;}
    try{this.check(frame);}catch(e){if(e.waiting){if(this.armed)void this.pause(e.message);}else void this.stop(e.message);return;}
    if(!this.ready)return;
    if(!this.armed){if(!this.stopping&&!this.pumping&&!this.connecting){try{this.arm(frame,true);}catch(e){this.notify(e.message);}}return;}
    this.latest=frame;
    if(!this.pumping)this.pumping=this.pump().catch(e=>{if(this.armed||!this.device?.gatt.connected)this.disconnect('Output interrupted: '+e.message,false);}).finally(()=>{this.pumping=null;});
  }
  async cached(i,key,bytes,ticket){const id=i+key,value=bytes.join(',');if(this.cache.get(id)===value)return;
    await this.write(this.channels[i][key],bytes,ticket);this.cache.set(id,value);}
  async pump(){const ticket=this.epoch;
    while(this.latest&&this.armed){const frame=this.latest;this.latest=null;this.valid(ticket);
      if(this.clock()-this.lastFrameAt>800)throw Error('Stale command frame');
      const ramp=Math.max(0,Math.min(1,(this.clock()-this.armedAt)/2000));
      for(let i=0;i<4;i++){this.valid(ticket);const c=frame.channels[i];const enabled=frame.config[i].enabled;
        const p=enabled?Math.round(c.power*ramp*10):0;
        if(p===0){await this.cached(i,'enable',[0],ticket);await this.cached(i,'power',[0,0],ticket);this.sent[i]=0;continue;}
        if(!this.cache.has(i+'enable')){await this.cached(i,'enable',[0],ticket);await this.cached(i,'power',[0,0],ticket);}
        await this.cached(i,'width',[Math.round(c.width),Math.round(c.width)],ticket);
        await this.cached(i,'frequency',[Math.round(c.frequency)],ticket);
        await this.cached(i,'power',[p&255,p>>8],ticket);await this.cached(i,'enable',[1],ticket);this.sent[i]=p/10;
      }
      this.notify('Output running; commands sent (not measured output)');
    }
  }
  stop(reason='Stopped',keepRequested=false){if(!keepRequested)this.requested=false;this.armed=false;this.latest=null;this.epoch++;
    if(this.stopping)return this.stopping;
    this.stopping=(async()=>{try{if(this.pumping)await this.pumping;if(this.device?.gatt.connected&&this.channels.length===4){await this.offAll();this.notify(reason+'; OFF and zero-power commands sent');}else this.notify(reason+'; hardware disconnected, output not measured');}catch(e){this.disconnect('Stop failed; disconnected: '+e.message,false);}
      })().finally(()=>{this.stopping=null;});return this.stopping;
  }
}
if(typeof module!=='undefined')module.exports={ZC95Output};
