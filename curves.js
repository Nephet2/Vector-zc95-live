'use strict';
const CurveMath={
 tangents(p){const h=p.slice(1).map((b,i)=>b[0]-p[i][0]),d=h.map((v,i)=>(p[i+1][1]-p[i][1])/v);if(d.length===1)return[d[0],d[0]];
 const end=(h0,h1,d0,d1)=>{let m=((2*h0+h1)*d0-h0*d1)/(h0+h1);if(m*d0<=0)return 0;return d0*d1<=0?Math.sign(m)*Math.min(Math.abs(m),3*Math.abs(d0)):m;};
 const m=[end(h[0],h[1],d[0],d[1])];for(let i=1;i<p.length-1;i++){const w1=2*h[i]+h[i-1],w2=h[i]+2*h[i-1];m.push(d[i-1]*d[i]<=0?0:(w1+w2)/(w1/d[i-1]+w2/d[i]));}return m.concat(end(h.at(-1),h.at(-2),d.at(-1),d.at(-2)));},
 evaluate(curve,position){const p=curve.points,x=Math.max(0,Math.min(100,position*100));let k=p.findIndex((_,i)=>i<p.length-1&&x<=p[i+1][0]);if(k<0)k=p.length-2;const a=p[k],b=p[k+1],h=b[0]-a[0],t=(x-a[0])/h;let y;if(curve.interpolation==='linear')y=a[1]+t*(b[1]-a[1]);else{const m=this.tangents(p);y=(2*t**3-3*t*t+1)*a[1]+(t**3-2*t*t+t)*h*m[k]+(-2*t**3+3*t*t)*b[1]+(t**3-t*t)*h*m[k+1];}return Math.max(Math.min(a[1],b[1]),Math.min(Math.max(a[1],b[1]),y))/100;},
 presets:{flat:[[0,100],[100,100]],rising:[[0,0],[100,100]],falling:[[0,100],[100,0]],triangle:[[0,0],[50,100],[100,0]],bell:[[0,0],[25,20],[50,100],[75,20],[100,0]],valley:[[0,100],[50,0],[100,100]],crossover_1:[[0,100],[40,100],[60,0],[100,0]],crossover_2:[[0,0],[40,0],[60,100],[100,100]]}
};
if(typeof module!=='undefined')module.exports=CurveMath;
