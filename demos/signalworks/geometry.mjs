import * as k from './anatomy-kit/iso-kit.mjs';
export const P=k.fitProjection([[-165,-90,-12],[175,90,0],[-50,20,110]],880,460,{pad:52,azimuth:48,elevation:30});
const parts=[];
function slab(id,x,y,w,d,z,h,tone='mid',lit=false){parts.push({id,point:[x+w/2,y+d/2,z+h/2],box:[x,y,z,x+w,y+d,z+h],html:k.solidSvg(k.slabOf({x,y,w,d,r:1},z,h,P,3,.5),{tone,lit})});}
for(const x of [-145,135])for(const y of [-65,65])slab('foot',x,y,14,14,-12,8,'lo');
slab('base',-160,-80,330,170,-4,8,'lo');
for(const x of [-135,125])for(const y of [-62,62]){slab('mount',x,y,18,14,4,3);slab('bolt',x+6,y+4,5,5,7,2,'hi');}
slab('bed',-135,-23,260,58,4,24);
for(let i=0;i<12;i++)slab('tread',-129+i*21,-18,18,48,28,3,'lo');
for(const y of [-26,34])slab('rail',-139,y,270,4,28,8);
for(const x of [-142,128])for(const y of [-28,31])slab('stop',x,y,5,10,28,12);
for(const x of [-38,6])for(const y of [-34,42]){slab('shoe',x-3,y-3,13,13,4,6);slab('post',x,y,7,7,10,82);}
slab('lintel',-41,-37,58,90,92,9,'hi');
slab('sensor',-24,-6,28,32,80,12,'hi');slab('aperture',-19,-1,18,22,78,2,'lo');
slab('receipt-pedestal',88,-20,39,54,31,8);slab('press-body',102,-15,22,44,39,31);slab('press-slide',90,-7,12,28,55,10,'hi');slab('stamp',80,-5,10,24,48,7,'hi');slab('receipt',77,-7,24,28,39,1,'hi');
slab('quarantine',-35,60,85,25,4,3,'lo');
for(const [x,y,w,d] of [[-35,60,85,3],[-35,82,85,3],[-35,63,3,19],[47,63,3,19]])slab('tray-rim',x,y,w,d,7,11);
slab('return',-125,55,62,25,4,3,'lo');slab('return-rim',-125,55,62,3,7,10);slab('return-rim',-125,77,62,3,7,10);
slab('controls',73,52,63,27,4,15);slab('switch-base',84,59,22,13,19,2,'lo');slab('switch',89,62,12,7,21,4,'hi');
const positions={ready:[-113,4,31],applied:[64,4,31],replayed:[-104,61,7],quarantined:[-8,66,7],rolled_back:[-26,4,31],blocked:[-26,4,31],stale:[-104,61,7]};
export const project=point=>k.iso(point,P);
// Axis-aligned solids use separating planes and projected convex hulls for painter order.
function hull(points){const p=points.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const cross=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);const half=xs=>{const h=[];for(const q of xs){while(h.length>1&&cross(h.at(-2),h.at(-1),q)<=0)h.pop();h.push(q);}return h;};return [...half(p).slice(0,-1),...half([...p].reverse()).slice(0,-1)];}
function outline(box){const [x,y,z,X,Y,Z]=box;return hull(k.boxCorners({x,y,w:X-x,d:Y-y,r:0},z,Z).map(p=>k.iso(p,P)));}
function overlap(a,b){for(const poly of [a,b])for(let i=0;i<poly.length;i++){const p=poly[i],q=poly[(i+1)%poly.length],axis=[p[1]-q[1],q[0]-p[0]];const project=xs=>xs.map(v=>v[0]*axis[0]+v[1]*axis[1]);const A=project(a),B=project(b);if(Math.max(...A)<=Math.min(...B)+.01||Math.max(...B)<=Math.min(...A)+.01)return false;}return true;}
function sorted(items){const edges=items.map(()=>[]),incoming=items.map(()=>0);const polygons=items.map(p=>p.outline||outline(p.box));for(let i=0;i<items.length;i++)for(let j=i+1;j<items.length;j++){if(!overlap(polygons[i],polygons[j]))continue;const a=items[i].box,b=items[j].box;const before=[0,1,2].some(d=>a[d+3]<=b[d]+.001),after=[0,1,2].some(d=>b[d+3]<=a[d]+.001);if(before&&!after){edges[i].push(j);incoming[j]++;}else if(after&&!before){edges[j].push(i);incoming[i]++;}}
const result=[],ready=items.map((_,i)=>i).filter(i=>incoming[i]===0);while(ready.length){ready.sort((a,b)=>k.depthOf(items[b].point,P)-k.depthOf(items[a].point,P));const i=ready.pop();result.push(items[i]);for(const j of edges[i])if(--incoming[j]===0)ready.push(j);}if(result.length!==items.length)throw Error('Painter order cycle');return result;}
for(const part of parts)part.outline=outline(part.box);
const parcelArt=k.solidSvg(k.slabOf({x:0,y:0,w:24,d:20,r:1},0,18,P,3,.7),{tone:'hi',lit:true})+k.solidSvg(k.slabOf({x:10,y:0,w:4,d:20,r:0},18,.6,P,1),{tone:'hi'});
export function machine(disposition='ready',fraction=1){
 const target=positions[disposition]||positions.ready, origin=positions.ready;
 const [x,y,z]=target.map((v,i)=>origin[i]+(v-origin[i])*fraction);
 const parcel={id:'parcel',point:[x+12,y+10,z+9],box:[x,y,z,x+24,y+20,z+18.6],html:`<g transform="${k.translateAlong(P,[x,y,z])}">${parcelArt}</g>`};
 return sorted([...parts,parcel]).map(p=>`<g data-part="${p.id}">${p.html}</g>`).join('');
}
export function svg(){return k.figureSvg({width:880,height:460,label:'Isometric parcel inspection machine. The red parcel represents the selected recorded event. Accessible controls and database results follow the illustration.',body:[machine()]});}
