'use strict';
const assert=require('assert'),fs=require('fs');global.setInterval=()=>0;global.ZC95Output=require('../bluetooth.js').ZC95Output;
const {ZC95WifiOutput}=require('../wifi.js');
function frame(){return{version:'0.9.1-wifi',neutral:false,config:[1,2,3,4].map(()=>({enabled:true})),channels:[1,2,3,4].map(channel=>({channel,state:'PREVIEW',power:80,frequency:90,width:120}))};}
function harness(){let now=0;const calls=[],h=new ZC95WifiOutput();h.clock=()=>now;h.ready=true;h.ws={readyState:1,close(){this.readyState=3;}};h.device={gatt:{get connected(){return h.ws.readyState===1;},disconnect(){h.ws.close();}}};h.channels=[{},{},{},{}];h.patternId=7;h.request=async(Type,body={})=>{calls.push({Type,...body});return{Result:'OK'};};return{h,calls,setTime:t=>now=t};}
async function tick(t,f=frame()){t.h.update(f);await t.h.pumping;}
(async()=>{
const t=harness();await t.h.stop('Before starting');assert.equal(t.h.stopping,null);t.h.arm(frame(),true);await t.h.pumping;assert.equal(t.calls[0].Type,'PatternStart');assert.equal(t.calls[1].Type,'SetPower');assert.equal(t.calls[1].Chan4,0);assert.equal(t.calls.at(-1).MenuId,13);assert.deepEqual(t.h.sent,[0,0,0,0]);
// Reported dials must drive remote power, not a full-scale remote ceiling.
t.h.receive({data:JSON.stringify({Type:'PowerStatus',MsgId:-1,Channels:[1000,500,250,0].map((PowerLimit,i)=>({Channel:i+1,PowerLimit}))})});
t.setTime(2000);await tick(t);
const remote=t.calls.filter(c=>c.Type==='SetPower').at(-1);assert.deepEqual([remote.Chan1,remote.Chan2,remote.Chan3,remote.Chan4],[1000,500,250,0]);
// Firmware remote-mode formula: min(Lua request * remote/1000, physical dial).
assert.deepEqual([1000,500,250,0].map((dial,i)=>Math.min(800*remote['Chan'+(i+1)]/1000,dial)),[800,400,200,0]);assert.deepEqual(t.h.sent,[80,80,80,80]);assert(t.calls.some(c=>c.MenuId===10&&c.NewValue===800));const n=t.calls.length;await tick(t);assert.equal(t.calls.length,n+1);assert.equal(t.calls.at(-1).MenuId,13);
t.h.receive({data:JSON.stringify({Type:'PowerStatus',MsgId:-1,Channels:[{Channel:2,PowerLimit:100}]})});await tick(t);assert.equal(t.calls.filter(c=>c.Type==='SetPower').at(-1).Chan2,100);
t.h.receive({data:JSON.stringify({Type:'PowerStatus',MsgId:-1,Channels:[{Channel:2,PowerLimit:2000}]})});assert.equal(t.h.dials[1],10);
await t.h.stop();assert(!t.h.requested);assert.deepEqual(t.calls.slice(-2).map(c=>[c.Type,c.MenuId,c.NewValue]),[['PatternMinMaxChange',13,0],['PatternStop',undefined,undefined]]);
const b=harness();let release;b.h.request=async(Type,body={})=>{b.calls.push({Type,...body});if(Type==='PatternMinMaxChange'&&body.MenuId===1)await new Promise(r=>release=r);return{Result:'OK'};};b.h.arm(frame(),true);for(let i=0;i<10&&!release;i++)await Promise.resolve();assert(release);const stopped=b.h.stop();release();await stopped;assert(!b.calls.some(c=>c.MenuId===13&&c.NewValue>0));assert(!b.h.requested);
const u=harness();u.h.arm(frame(),true);await u.h.pumping;u.setTime(2000);const f=frame();f.channels[3].state='STALE / NO INPUT';u.h.update(f);await u.h.stopping;assert(!u.h.armed);assert(u.h.requested);

// Full protocol setup: installed receiver, empty-slot upload, and no overwrite.
const logs=[];global.document={getElementById:()=>({value:'192.168.86.41'})};
let mode='installed',messages=[];
global.fetch=async()=>({ok:true,text:async()=>fs.readFileSync(require('path').join(__dirname,'../vector_wifi.lua'),'utf8')});
global.WebSocket=class{
 constructor(url){assert.equal(url,'ws://192.168.86.41/stream');this.readyState=0;queueMicrotask(()=>{this.readyState=1;this.onopen();});}
 send(json){const m=JSON.parse(json);messages.push(m);let body={};
 if(m.Type==='GetVersion')body={ZC95:'mock'};
 if(m.Type==='GetLuaScripts')body={Scripts:mode==='installed'?[{Index:2,Valid:true,Name:'U:Vector WiFi v1'}]:mode==='empty'?[{Index:3,Empty:true}]:[{Index:0,Empty:false,Valid:true,Name:'U:Keep me'}]};
 if(m.Type==='GetPatterns')body={Patterns:[{Id:9,Name:'U:Vector WiFi v1'}]};
 if(m.Type==='GetPatternDetail')body={MenuItems:Array.from({length:13},(_,i)=>({Id:i+1,Type:'MIN_MAX'}))};
 queueMicrotask(()=>this.onmessage({data:JSON.stringify({Type:'Ack',MsgId:m.MsgId,Result:'OK',...body})}));}
 close(){if(this.readyState===3)return;this.readyState=3;this.onclose?.();}
};
let h=new ZC95WifiOutput(s=>logs.push(s.message));await h.connect();assert(h.ready);assert.equal(h.patternId,9);assert(!messages.some(m=>m.Type==='PatternStart'||m.Type==='LuaStart'));h.disconnect();
mode='empty';messages=[];h=new ZC95WifiOutput();await h.connect();assert(h.ready);assert.equal(messages.find(m=>m.Type==='LuaStart').Index,3);assert(messages.some(m=>m.Type==='LuaEnd'));assert(messages.filter(m=>m.Type==='LuaLine').length>30);h.disconnect();
mode='full';messages=[];h=new ZC95WifiOutput(s=>logs.push(s.message));await h.connect();assert(!h.ready);assert(!messages.some(m=>m.Type==='LuaStart'));assert(logs.some(s=>s.includes('No empty Lua slot')));
console.log('WiFi pump passed: staged four-channel frames, commit heartbeat, startup ramp, Stop, stale input and cancellation.');
})().catch(e=>{console.error(e);process.exitCode=1;});
