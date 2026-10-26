'use strict';
const assert=require('assert');global.CurveMath=require('../curves.js');const R=require('../ribbon.js');
const curves=['crossover_1','bell','triangle','crossover_2'].map(k=>({points:CurveMath.presets[k],interpolation:'smooth'}));
const channels=curves.map((c,i)=>({enabled:true,state:'PREVIEW',position:.5,weight:CurveMath.evaluate(c,.5)*100}));
const before=JSON.stringify(channels);
for(const yaw of [-75,-24,0,75])for(const pitch of [10,25,70]){const svg=R.render(curves,channels,{yaw,pitch});assert(!/NaN|Infinity|undefined/.test(svg));assert.equal((svg.match(/<circle/g)||[]).length,4);assert(svg.includes('stroke-dasharray="4 5"'));for(const m of svg.matchAll(/<circle cx="([^"]+)" cy="([^"]+)"/g)){assert(Number(m[1])>0&&Number(m[1])<1000);assert(Number(m[2])>0&&Number(m[2])<350);}}
const offline=channels.map(c=>({...c,state:'OFFLINE'}));assert(!R.render(curves,offline,{yaw:-24,pitch:25}).includes('<circle'));
const preview=R.render(curves,offline,{yaw:-24,pitch:25},{live:false,position:.25});assert.equal((preview.match(/<circle/g)||[]).length,4);
const mixed=channels.map((c,i)=>({...c,position:i/3}));assert(!R.render(curves,mixed,{yaw:-24,pitch:25}).includes('stroke-dasharray="4 5"'));
assert.equal(JSON.stringify(channels),before);
console.log('3D ribbons passed: camera bounds, finite projection, shared/independent markers, offline state and read-only preview.');
