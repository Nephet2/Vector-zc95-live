'use strict';
// Wi-Fi native pattern playback. Vector frames never enter this mode.
const patternBase={maintain:ZC95WifiOutput.prototype.maintain,offAll:ZC95WifiOutput.prototype.offAll,update:ZC95WifiOutput.prototype.update};
Object.assign(ZC95WifiOutput.prototype,{
 async patternTask(work,quiet=false){
  if(!this.patternMode||!this.ready||this.connecting||this.stopping)throw Error('Connect Wi-Fi in Pattern player mode and wait for the current operation');
  const ticket=this.epoch;while(this.pumping){await this.pumping;this.valid(ticket);}if(this.stopping)throw Error('Output stopping');this.patternBusy=!quiet;if(!quiet)this.notify(this.message);
  const job=Promise.resolve().then(()=>work(ticket));this.pumping=job;
  try{return await job;}finally{if(this.pumping===job)this.pumping=null;this.patternBusy=false;this.notify(this.message);}
 },
 async listPatterns(){return this.patternTask(async ticket=>{const r=await this.request('GetPatterns');this.valid(ticket);this.patternList=(r.Patterns||[]).filter(p=>!p.Name.startsWith('U:Vector WiFi'));return this.patternList;});},
 async patternDetail(id){return this.patternTask(async ticket=>{const r=await this.request('GetPatternDetail',{Id:Number(id)});this.valid(ticket);this.selectedPattern=r;return r;});},
 async playPattern(){return this.patternTask(async ticket=>{
  if(this.suspended)throw Error('Keep this tab visible before starting');
  if(this.patternRunning)throw Error('Pattern already playing');if(!this.selectedPattern)throw Error('Select a pattern first');
  this.dials=[null,null,null,null];
  await this.request('PatternStart',{Index:this.selectedPattern.Id});this.patternRunning=true;this.valid(ticket);
  await this.request('SetPower',{Chan1:0,Chan2:0,Chan3:0,Chan4:0});this.valid(ticket);
  this.armed=true;this.requested=true;this.armedAt=this.clock();this.nextPatternBeat=0;
  this.notify('Pattern playing: '+this.selectedPattern.Name);
 });},
 async changePatternValue(item,value){return this.patternTask(async ticket=>{
  if(!this.patternRunning)throw Error('Press Play before adjusting pattern controls');
  if(item.Type==='MIN_MAX'){
   const n=Number(value);if(!Number.isInteger(n)||n<item.Min||n>item.Max)throw Error('Value outside pattern range');
   await this.request('PatternMinMaxChange',{MenuId:item.Id,NewValue:n});
  }else if(item.Type==='MULTI_CHOICE'){
   const n=Number(value);if(!(item.Choices||[]).some(c=>c.Id===n))throw Error('Invalid pattern choice');
   await this.request('PatternMultiChoiceChange',{MenuId:item.Id,ChoiceId:n});
  }else throw Error('Unsupported control');
  this.valid(ticket);this.notify('Pattern setting updated');
 });},
 async patternButton(){return this.patternTask(async ticket=>{
  if(!this.patternRunning)throw Error('No pattern playing');
  try{await this.request('PatternSoftButton',{Pressed:1});await new Promise(r=>setTimeout(r,100));this.valid(ticket);}
  finally{if(this.ws?.readyState===1&&this.patternRunning)await this.request('PatternSoftButton',{Pressed:0});}
 });},
 pause(reason){if(this.patternMode)return this.stop(reason,false);return ZC95Output.prototype.pause.call(this,reason);},
 update(frame){if(!this.patternMode)return patternBase.update.call(this,frame);},
 maintain(){
  if(!this.patternMode)return patternBase.maintain.call(this);
  if(this.patternRunning&&this.armed&&!this.pumping&&!this.stopping&&this.clock()>=(this.nextPatternBeat||0)){
   this.nextPatternBeat=this.clock()+400;
   void this.patternTask(async ticket=>{
    const ramp=Math.max(0,Math.min(1,(this.clock()-this.armedAt)/2000));
    const levels=this.dials.map(v=>Number.isFinite(v)?Math.round(v*10*ramp):0);
    await this.request('SetPower',Object.fromEntries(levels.map((v,i)=>['Chan'+(i+1),v])));this.valid(ticket);
   },true).catch(e=>{if(!this.stopping)this.disconnect('Pattern connection interrupted: '+e.message);});
  }else if(!this.patternRunning&&!this.pumping&&!this.stopping&&!this.connecting){
   // Idle heartbeat only. Patterns never automatically restart after a loss.
   const requested=this.requested;this.requested=false;patternBase.maintain.call(this);this.requested=requested;
  }
 },
 async offAll(){
  if(this.patternRunning){
   if(this.ws?.readyState===1){await this.request('SetPower',{Chan1:0,Chan2:0,Chan3:0,Chan4:0});await this.request('PatternStop');}
   this.patternRunning=false;this.sent=[0,0,0,0];return;
  }
  return patternBase.offAll.call(this);
 }
});
Object.assign(ZC95WifiOutput.prototype,{
 async uploadPattern(text){
  if(typeof text!=='string'||!text.trim()||new TextEncoder().encode(text).length>65536)throw Error('Choose a nonempty Lua file smaller than 64 KB');
  text=text.replace(/^\uFEFF/,'');
  if(/Vector WiFi/.test(text))throw Error('The Vector receiver is managed automatically; select your own Lua pattern');
  return this.patternTask(async ticket=>{
   if(this.patternRunning||this.requested)throw Error('Stop output before uploading');
   const r=await this.request('GetLuaScripts');this.valid(ticket);
   const slot=(r.Scripts||[]).find(s=>s.Empty);if(!slot)throw Error('No empty Lua slot; existing scripts were kept');
   let loading=false;
   try{
    await this.request('LuaStart',{Index:slot.Index});loading=true;this.valid(ticket);
    const lines=text.split(/\r?\n/);
    for(let i=0;i<lines.length;i++){this.valid(ticket);await this.request('LuaLine',{LineNumber:i,Text:lines[i]});}
    await this.request('LuaEnd',{},5000);loading=false;this.valid(ticket);
    this.selectedPattern=null;this.patternId=null;this.notify('Lua uploaded to empty slot '+slot.Index+'; output remains stopped');
   }catch(e){if(loading)this.disconnect('Lua upload interrupted; reconnect before continuing');throw e;}
  });
 }
});
function initialisePatterns(){
 const w=hardware.wifi,el=id=>document.getElementById(id);
 const fail=e=>{el('patternNote').textContent=e.message;};
 async function task(fn){try{await fn();}catch(e){fail(e);}finally{window.refreshPatternUI();}}
 async function load(){
  const list=await w.listPatterns();el('patternList').replaceChildren();
  for(const p of list){const o=document.createElement('option');o.value=p.Id;o.textContent=p.Name;el('patternList').append(o);}
  if(list.length)await detail();else{w.selectedPattern=null;el('patternControls').replaceChildren();}
  el('patternNote').textContent='Select a pattern, then Play. Physical dials control power; Vector curves are retained.';
 }
 async function detail(){
  const d=await w.patternDetail(el('patternList').value);el('patternControls').replaceChildren();
  for(const item of d.MenuItems||[]){
   const label=document.createElement('label');label.textContent=item.Title||'Control '+item.Id;let input;
   if(item.Type==='MIN_MAX'){
    input=document.createElement('input');input.type='number';input.min=item.Min;input.max=item.Max;input.step=item.IncrementStep||1;input.value=item.Default;label.textContent+=' '+(item.UoM||'');
   }else if(item.Type==='MULTI_CHOICE'){
    input=document.createElement('select');for(const c of item.Choices||[]){const o=document.createElement('option');o.value=c.Id;o.textContent=c.Name;input.append(o);}input.value=item.Default;
   }else{const note=document.createElement('span');note.textContent=' Display supplied by device ('+item.Type+')';label.append(note);el('patternControls').append(label);continue;}
   input.dataset.patternControl='1';input.disabled=!w.patternRunning;
   input.onchange=()=>task(async()=>{try{await w.changePatternValue(item,input.value);input.dataset.accepted=input.value;}catch(e){input.value=input.dataset.accepted;throw e;}});input.dataset.accepted=input.value;
   label.append(input);el('patternControls').append(label);
  }
  el('patternSoft').textContent=d.ButtonA||'Pattern button';el('patternSoft').hidden=!d.ButtonA;
 }
 el('outputMode').onchange=()=>task(async()=>{
  await hardware.stop('Output mode changed');w.patternMode=el('outputMode').value==='patterns';w.selectedPattern=null;
  el('patternPlayer').hidden=!w.patternMode;el('hwStart').hidden=w.patternMode;
  if(w.patternMode&&w.ready)await load();
  if(!w.patternMode&&w.ready){w.disconnect('Reconnect Wi-Fi to reload the Vector receiver after changing mode');}
 });
 el('patternRefresh').onclick=()=>task(load);
 el('patternList').onchange=()=>task(async()=>{await hardware.stop('Pattern selection changed');await detail();});
 el('patternPlay').onclick=()=>task(async()=>{await detail();try{await w.playPattern();}catch(e){await w.stop('Pattern start failed');throw e;}});el('patternStop').onclick=()=>hardware.stop('Pattern stopped');
 el('patternSoft').onclick=()=>task(()=>w.patternButton());
 el('patternUpload').onclick=()=>task(async()=>{const file=el('patternFile').files[0];if(!file||!file.name.toLowerCase().endsWith('.lua'))throw Error('Choose a .lua file');await w.uploadPattern(await file.text());await load();el('patternNote').textContent='Lua uploaded; select it from the list. Output remains stopped.';});
 window.refreshPatternUI=()=>{
  const wifi=hardware.mode==='wifi',busy=!!(w.patternBusy||w.connecting||w.stopping),playing=!!w.patternRunning;
  el('outputModeLabel').hidden=!wifi;el('hwStart').hidden=wifi&&!!w.patternMode;el('patternPlayer').hidden=!wifi||!w.patternMode;
  el('patternPlay').disabled=!w.ready||busy||playing||!w.selectedPattern;
  el('patternStop').disabled=!w.ready;el('patternRefresh').disabled=!w.ready||busy||playing;
  el('patternUpload').disabled=!w.ready||busy||playing;el('patternFile').disabled=busy||playing;
  el('patternList').disabled=!w.ready||busy||playing;el('patternSoft').disabled=!playing||busy;
  for(const input of el('patternControls').querySelectorAll('[data-pattern-control]'))input.disabled=!playing||busy;
  if(wifi&&w.patternMode){el('hwStart').disabled=true;el('hwSent').textContent=playing?'Native pattern playing; physical dials set power. Vector curves and meters are preview only.':'Pattern player stopped; press Refresh patterns after connecting.';}
 };
 window.refreshPatternUI();
}
