import test from 'node:test';
import assert from 'node:assert/strict';
import {createPlayer} from './player.mjs';
const traces={scenarios:[{id:'a',steps:[{n:0},{n:1},{n:2}]},{id:'b',steps:[{n:9}]}]};
function setup(){let callback;let cleared=0;const changes=[];const p=createPlayer(traces,s=>changes.push(s),{schedule:fn=>(callback=fn,1),cancel:()=>cleared++});return {p,changes,tick:()=>callback(),cleared:()=>cleared};}
test('step bounds and reset',()=>{const {p}=setup();p.step();p.step();p.step();assert.equal(p.state.index,2);p.reset();assert.equal(p.state.index,0);});
test('selection cancels pending playback and stale callbacks',()=>{const x=setup();x.p.play();x.p.select('b');x.tick();assert.equal(x.p.state.step.n,9);assert.equal(x.p.state.playing,false);assert.ok(x.cleared()>0);});
test('reset cancels playback',()=>{const x=setup();x.p.play();x.p.reset();x.tick();assert.equal(x.p.state.index,0);assert.equal(x.p.state.playing,false);});
test('pause and destroy prevent subsequent ticks',()=>{const x=setup();x.p.play();x.p.pause();x.tick();assert.equal(x.p.state.index,0);x.p.destroy();assert.throws(()=>x.p.play(),/destroyed/);});
test('missing traces fail explicitly',()=>{assert.throws(()=>createPlayer({scenarios:[]},()=>{}),/No recorded/);});
test('unknown scenario preserves current state',()=>{const {p}=setup();assert.throws(()=>p.select('missing'),/Unknown/);assert.equal(p.state.scenario.id,'a');});
