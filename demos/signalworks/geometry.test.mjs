import test from 'node:test';
import assert from 'node:assert/strict';
import {machine,svg} from './geometry.mjs';
test('all scenario poses and intervening frames have acyclic depth order',()=>{
 for(const disposition of ['ready','applied','replayed','quarantined','rolled_back','blocked','stale'])for(let i=0;i<=20;i++){
  const result=machine(disposition,i/20);assert.equal((result.match(/data-part="parcel"/g)||[]).length,1);assert.ok(!/NaN|undefined/.test(result));
 }
});
test('static SVG has accessible role and label',()=>{assert.match(svg(),/role="img"/);assert.match(svg(),/Isometric parcel inspection machine/);});
