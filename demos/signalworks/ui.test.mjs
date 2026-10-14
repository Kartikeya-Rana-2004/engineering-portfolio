import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
function environment(data){
 const elements=new Map(),windowEvents={};
 const el=id=>{if(!elements.has(id))elements.set(id,{textContent:'',disabled:true,value:'',dataset:{},events:{},addEventListener(n,f){this.events[n]=f;},setAttribute(){},replaceChildren(){}});return elements.get(id);};
 globalThis.document={getElementById:el,querySelectorAll:()=>[],querySelector:()=>el('stage'),createElement:()=>el(Symbol()),documentElement:{dataset:{}},addEventListener(){}};
 globalThis.matchMedia=()=>({matches:true,addEventListener(){}});
 globalThis.fetch=async()=>({ok:true,json:async()=>data});
 globalThis.cancelAnimationFrame=()=>{};
 globalThis.IntersectionObserver=class{observe(){}disconnect(){}};
 globalThis.window={addEventListener(n,f){windowEvents[n]=f;}};
 return {el,windowEvents};
}
const traces=()=>JSON.parse(readFileSync(new URL('./traces.json',import.meta.url)));
test('invalid future trace leaves explicit fallback with disabled controls',async()=>{
 const data=traces();delete data.scenarios[0].steps[1].state;const {el}=environment(data);
 await import('./ui.mjs?invalid');await new Promise(r=>setTimeout(r,0));
 assert.equal(el('play').disabled,true);assert.equal(el('scenario-title').textContent,'Recorded run unavailable');
});
test('BFCache restore keeps a usable player',async()=>{
 const {el,windowEvents}=environment(traces());await import('./ui.mjs?bfcache');await new Promise(r=>setTimeout(r,0));
 windowEvents.pagehide({persisted:true});
 assert.doesNotThrow(()=>el('step').events.click());assert.equal(el('checkpoint').textContent,'1');
 // Stop any timers and cleanly dispose the player for the test process.
 windowEvents.pagehide({persisted:false});
});
