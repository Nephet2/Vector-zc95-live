const assert=require('assert');
const timers=[];global.setInterval=fn=>{timers.push(fn);return timers.length;};
const {ZC95Output}=require('../bluetooth.js');
function frame(){return{version:'0.9.2-wifi',neutral:false,config:[{enabled:true},{enabled:true},{enabled:true},{enabled:true}],channels:[1,2,3,4].map(i=>({channel:i,state:'PREVIEW',power:80,frequency:80,width:100}))};}
function harness(){let now=0;const writes=[];const h=new ZC95Output();h.clock=()=>now;h.device={gatt:{connected:true,disconnect(){this.connected=false;}}};h.ready=true;h.channels=[0,1,2,3].map(i=>Object.fromEntries(['enable','power','width','frequency'].map(key=>[key,{async writeValueWithoutResponse(bytes){writes.push([i+1,key,[...bytes]]);}}])));return{h,writes,setTime:n=>now=n};}
async function tick(t,f=frame()){t.h.update(f);if(t.h.pumping)await t.h.pumping;}
(async()=>{
// Curve-preset stop before connecting must settle its latch before Start.
{const t=harness();t.h.device.gatt.connected=false;t.h.ready=false;
await t.h.stop('Curve preset changed');assert.strictEqual(t.h.stopping,null);
t.h.device.gatt.connected=true;t.h.ready=true;t.h.arm(frame(),true);await t.h.pumping;
t.setTime(2000);await tick(t);assert.equal(t.h.sent[3],80);await t.h.stop();}
{const h=new ZC95Output();await h.stop('Before device selection');assert.strictEqual(h.stopping,null);}

let t=harness();assert.throws(()=>t.h.arm({...frame(),channels:frame().channels.slice(0,3)},true),/four-channel/);const bad=frame();bad.channels[0].power=101;assert.throws(()=>t.h.arm(bad,true),/Invalid/);assert.throws(()=>t.h.arm(frame(),false),/Scale/);assert.throws(()=>t.h.arm({...frame(),neutral:true},true),/Neutral/);assert(!t.writes.length);
t.h.arm(frame(),true);await t.h.pumping;t.setTime(2000);await tick(t);assert.deepEqual(t.h.sent.slice(0,3),[80,80,80]);assert(t.writes.some(w=>w[0]===4&&w[1]==='enable'&&w[2][0]===1));assert.equal(t.h.sent[3],80);assert(t.writes.filter(w=>w[1]==='width').every(w=>w[2][0]===100&&w[2][1]===100));assert(t.writes.filter(w=>w[1]==='power').every(w=>(w[2][0]+w[2][1]*256)<=800));
await t.h.stop('test');assert.deepEqual(t.h.sent,[0,0,0,0]);assert(!t.h.armed);assert(t.h.device.gatt.connected);assert.deepEqual(t.writes.slice(-8),[...[1,2,3,4].map(i=>[i,'enable',[0]]),...[1,2,3,4].map(i=>[i,'power',[0,0]])]);
t=harness();t.h.arm(frame(),true);await t.h.pumping;t.setTime(2000);let f=frame();f.config[1].enabled=false;await tick(t,f);assert.equal(t.h.sent[1],0);f=frame();f.channels[0].state='STALE / NO INPUT';t.h.update(f);await t.h.stopping;assert(!t.h.armed);assert.deepEqual(t.h.sent,[0,0,0,0]);
t=harness();t.h.arm(frame(),true);await t.h.pumping;t.setTime(900);timers.at(-1)();await t.h.stopping;assert(!t.h.armed);
t=harness();t.h.arm(frame(),true);await t.h.pumping;t.setTime(3600000);t.h.lastFrameAt=3600000;timers.at(-1)();assert(t.h.armed);await tick(t);assert(t.h.armed);await t.h.stop();
t=harness();t.h.arm(frame(),true);await t.h.pumping;t.setTime(2000);let release;t.h.channels[0].width.writeValueWithoutResponse=()=>new Promise(r=>release=r);t.h.update(frame());await new Promise(r=>setImmediate(r));const before=t.writes.length;const stopped=t.h.stop('cancel');release();await stopped;assert(!t.writes.slice(before).some(w=>w[1]==='enable'&&w[2][0]===1));assert.deepEqual(t.h.sent,[0,0,0,0]);
t=harness();t.h.arm(frame(),true);await t.h.pumping;t.setTime(2000);t.h.channels[0].width.writeValueWithoutResponse=async()=>{throw Error('link fault');};await tick(t);assert(!t.h.armed);assert(!t.h.device.gatt.connected);const count=t.writes.length;t.h.update(frame());assert.equal(t.writes.length,count);assert(t.h.requested);
t=harness();f=frame();f.channels[0].power=37.5;f.channels[1].power=100;f.channels[2].power=0;t.h.arm(f,true);await t.h.pumping;t.setTime(2000);await tick(t,f);assert.deepEqual(t.h.sent.slice(0,3),[37.5,100,0]);assert(t.writes.some(w=>w[0]===1&&w[1]==='power'&&w[2][0]===119&&w[2][1]===1));assert(t.writes.some(w=>w[0]===2&&w[1]==='power'&&w[2][0]===232&&w[2][1]===3));await t.h.stop();
t=harness();t.h.arm(frame(),true);await t.h.pumping;f=frame();f.channels[0].state='STALE / NO INPUT';t.h.update(f);await t.h.stopping;assert(t.h.requested);assert(!t.h.armed);t.setTime(1000);await tick(t);assert(t.h.armed);assert.deepEqual(t.h.sent.slice(0,3),[0,0,0]);t.setTime(3000);await tick(t);assert.equal(t.h.sent[0],80);await t.h.stop('manual');assert(!t.h.requested);await tick(t);assert(!t.h.armed);
t=harness();t.h.arm(frame(),true);await t.h.pumping;t.h.disconnect('lost link',false);assert(t.h.requested);assert(!t.h.armed);let retries=0;t.h.connect=async reuse=>{assert(reuse);retries++;};t.setTime(100);t.h.lastFrameAt=100;t.h.maintain();assert.equal(retries,1);await t.h.stop('manual while reconnecting');t.setTime(6000);t.h.lastFrameAt=6000;t.h.maintain();assert.equal(retries,1);
t=harness();t.h.arm(frame(),true);await t.h.pumping;t.h.disconnect('unexpected',false);let chooserCalls=0;if(!global.navigator)global.navigator={};global.navigator.bluetooth={requestDevice:async()=>{chooserCalls++;throw Error('chooser must not reopen');}};
const characteristic={writeValueWithoutResponse:async()=>{},readValue:async()=>new DataView(new ArrayBuffer(2)),startNotifications:async()=>{},addEventListener(){},removeEventListener(){}};
t.h.device.gatt={connected:false,async connect(){this.connected=true;return this;},disconnect(){this.connected=false;},async getPrimaryService(name){if(name==='device_information'||name==='battery_service')throw Error('optional');return{getCharacteristic:async()=>characteristic};}};
await t.h.connect(true);assert.equal(chooserCalls,0);assert(t.h.ready);assert(t.h.requested);assert(!t.h.armed);await tick(t);assert(t.h.armed);await t.h.stop();assert(!t.h.requested);t.h.disconnect();
t=harness();f=frame();f.config[3].enabled=false;t.h.arm(f,true);await t.h.pumping;t.setTime(2000);await tick(t,f);assert.equal(t.h.sent[3],0);assert(!t.writes.some(w=>w[0]===4&&w[1]==='enable'&&w[2][0]===1));await t.h.stop();
console.log('Four-channel BLE checks passed: direct full-range commands, Scale prerequisite, balanced widths, disabled/stale input, continuous run, feed watchdog, cancellation, automatic reconnect/resume and latched manual stop.');
})().catch(e=>{console.error(e);process.exitCode=1;});
