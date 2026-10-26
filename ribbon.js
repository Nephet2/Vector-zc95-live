'use strict';
const RibbonView={
 project(x,y,z,c){const a=c.yaw*Math.PI/180,b=c.pitch*Math.PI/180,u=x*Math.cos(a)+z*Math.sin(a),v=-x*Math.sin(a)+z*Math.cos(a);return[u,-y*Math.cos(b)+v*Math.sin(b),y*Math.sin(b)+v*Math.cos(b)];},
 render(curves,channels,camera,{live=true,position=.5,dirty=false}={}){
  if(curves.length!==4)return'';
  const corners=[];for(const x of [-1.2,1.2])for(const y of [0,1.1])for(const z of [-1,1])corners.push(this.project(x,y,z,camera));
  const minX=Math.min(...corners.map(p=>p[0])),maxX=Math.max(...corners.map(p=>p[0])),minY=Math.min(...corners.map(p=>p[1])),maxY=Math.max(...corners.map(p=>p[1]));
  const scale=1.3*Math.min(800/(maxX-minX),255/(maxY-minY));const project=(x,y,z)=>{const p=this.project(x,y,z,camera);return[500+(p[0]-(minX+maxX)/2)*scale,168+(p[1]-(minY+maxY)/2)*scale,p[2]];};
  const xyz=(x,y,i)=>project((x-.5)*2.4,y*1.1,(1.5-i)*.56),coord=p=>p.slice(0,2).map(v=>v.toFixed(2)).join(','),path=pts=>'M'+pts.map(coord).join('L');
  const colour=['#7ddfcb','#f1b095','#adadff','#ecd17e'];let svg='';
  const line=(a,b,stroke='#43566d',extra='')=>`<path d="${path([a,b])}" fill="none" stroke="${stroke}" ${extra}/>`;
  const label=(p,t,fill='#acbed2',dy=0)=>`<text x="${p[0].toFixed(2)}" y="${(p[1]+dy).toFixed(2)}" fill="${fill}" font-size="12" text-anchor="middle" paint-order="stroke" stroke="#121d2c" stroke-width="3">${t}</text>`;
  for(let n=0;n<=4;n++){const x=n/4;svg+=line(xyz(x,0,0),xyz(x,0,3))+label(xyz(x,0,0),n*25+'%',undefined,20);}
  for(let i=0;i<4;i++)svg+=line(xyz(0,0,i),xyz(1,0,i))+label(xyz(1.08,0,i),'Ch '+(i+1),colour[i],4);
  svg+=line(xyz(0,0,0),xyz(0,1,0));for(const y of [.5,1])svg+=label(xyz(-.07,y,0),Math.round(y*100)+'%');
  const faces=[];for(let i=0;i<4;i++)for(let n=0;n<80;n++){const a=n/80,b=(n+1)/80,ya=CurveMath.evaluate(curves[i],a),yb=CurveMath.evaluate(curves[i],b),pts=[xyz(a,0,i),xyz(a,ya,i),xyz(b,yb,i),xyz(b,0,i)];faces.push({depth:pts.reduce((v,p)=>v+p[2],0)/4,html:`<path d="${path(pts)}Z" fill="${colour[i]}" fill-opacity="${channels[i]?.enabled===false?0.06:0.24}" stroke="none"/>`});}
  svg+=faces.sort((a,b)=>a.depth-b.depth).map(f=>f.html).join('');
  const order=[0,1,2,3].sort((a,b)=>xyz(.5,.5,a)[2]-xyz(.5,.5,b)[2]);
  const moving=channels.filter(c=>c&&c.enabled!==false&&['PREVIEW','GATED OFF','BACKGROUND'].includes(c.state));
  if(!live||moving.length&&moving.every(c=>Math.abs(c.position-moving[0].position)<.001)){const x=live?moving[0].position:position;svg+=`<path d="${path([xyz(x,0,0),xyz(x,1,0),xyz(x,1,3),xyz(x,0,3)])}Z" fill="#e7eef8" fill-opacity=".045" stroke="#c3d2e4" stroke-opacity=".4" stroke-dasharray="4 5"/>`;}
  for(const i of order){const c=channels[i],enabled=c?.enabled!==false;const pts=Array.from({length:161},(_,n)=>xyz(n/160,CurveMath.evaluate(curves[i],n/160),i));svg+=`<path d="${path(pts)}" fill="none" stroke="${colour[i]}" stroke-width="2.5" opacity="${enabled?1:.25}"/>`;
   if(enabled&&(!live||['PREVIEW','GATED OFF','BACKGROUND'].includes(c?.state))){const x=live?c.position:position,y=live?c.weight/100:CurveMath.evaluate(curves[i],position),p=xyz(x,y,i);svg+=line(xyz(x,0,i),p,colour[i],'stroke-dasharray="3 3"')+`<circle cx="${p[0].toFixed(2)}" cy="${p[1].toFixed(2)}" r="5" fill="${colour[i]}" stroke="#fff"/>`+label(p,'Ch '+(i+1)+' '+(y*100).toFixed(0)+'%',colour[i],-12);}}
  svg+=`<text x="25" y="330" fill="#acbed2" font-size="12">Position →   ·   Depth: channel   ·   Height: curve response above background</text>`;
  return svg;
 }
};
let ribbonCamera={yaw:-24,pitch:25},ribbonDrag=null,ribbonOffline=false;
function drawRibbon(){const svg=$('ribbonPlot');if(!svg||$('ribbonWrap').hidden||typeof curves==='undefined'||curves.length!==4)return;const live=$('ribbonLive').checked,channels=(state?.channels||[]).map((c,i)=>({...c,state:ribbonOffline?'OFFLINE':c.state,enabled:$('channel'+i).querySelector('[data-key="enabled"]').checked}));svg.innerHTML=RibbonView.render(curves,channels,ribbonCamera,{live,position:Number($('ribbonPosition').value)/100,dirty});$('ribbonStatus').textContent=(live?(ribbonOffline?'Live feed offline':channels.some(c=>c.enabled&&['PREVIEW','BACKGROUND','GATED OFF'].includes(c.state))?'Live applied markers':'Waiting for input; untick Live markers to preview'):'View-only preview: '+$('ribbonPosition').value+'%')+(dirty?' · Curves pending autosave':'')+' · Drag to rotate';}
function initialiseRibbon(){const svg=$('ribbonPlot');if(!svg)return;
 $('ribbonToggle').onclick=()=>{const hidden=$('ribbonWrap').hidden;$('ribbonWrap').hidden=!hidden;$('graph').hidden=hidden;$('ribbonToggle').textContent=hidden?'Show 2D':'Show 3D';drawRibbon();};
 $('ribbonLive').onchange=()=>{$('ribbonPosition').disabled=$('ribbonLive').checked;drawRibbon();};$('ribbonPosition').oninput=drawRibbon;
 const sync=()=>{$('ribbonYaw').value=ribbonCamera.yaw;$('ribbonPitch').value=ribbonCamera.pitch;drawRibbon();};
 $('ribbonYaw').oninput=()=>{ribbonCamera.yaw=Number($('ribbonYaw').value);drawRibbon();};$('ribbonPitch').oninput=()=>{ribbonCamera.pitch=Number($('ribbonPitch').value);drawRibbon();};$('ribbonHome').onclick=()=>{ribbonCamera={yaw:-24,pitch:25};sync();};
 svg.addEventListener('pointerdown',e=>{ribbonDrag={id:e.pointerId,x:e.clientX,y:e.clientY,...ribbonCamera};svg.setPointerCapture(e.pointerId);e.preventDefault();});
 svg.addEventListener('pointermove',e=>{if(!ribbonDrag||ribbonDrag.id!==e.pointerId)return;ribbonCamera={yaw:Math.max(-75,Math.min(75,ribbonDrag.yaw+(e.clientX-ribbonDrag.x)*.25)),pitch:Math.max(10,Math.min(70,ribbonDrag.pitch+(e.clientY-ribbonDrag.y)*.2))};sync();});
 for(const k of ['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(k,e=>{if(ribbonDrag?.id===e.pointerId)ribbonDrag=null;});
}
if(typeof module!=='undefined')module.exports=RibbonView;
