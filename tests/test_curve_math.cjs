'use strict';
const assert=require('assert'),C=require('../curves.js');
let seed=47;const rand=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};
for(let n=0;n<100;n++){const xs=[0,10,25,50,80,100],points=xs.map(x=>[x,rand()*100]);for(const interpolation of ['linear','smooth']){const c={points,interpolation};for(const [x,y] of points)assert(Math.abs(C.evaluate(c,x/100)-y/100)<1e-10);for(let k=0;k<points.length-1;k++){const a=points[k],b=points[k+1];let prev=C.evaluate(c,a[0]/100);for(let j=1;j<=100;j++){const y=C.evaluate(c,(a[0]+(b[0]-a[0])*j/100)/100);assert(y>=Math.min(a[1],b[1])/100-1e-10&&y<=Math.max(a[1],b[1])/100+1e-10);assert((y-prev)*(b[1]-a[1])>=-1e-10);prev=y;}}}}
for(let n=0;n<=100;n++){const a={points:C.presets.crossover_1,interpolation:'linear'},b={points:C.presets.crossover_2,interpolation:'linear'};assert(Math.abs(C.evaluate(a,n/100)+C.evaluate(b,n/100)-1)<1e-10);}
console.log('Curve math passed: exact knots, bounded monotonic segments and complementary crossover.');
