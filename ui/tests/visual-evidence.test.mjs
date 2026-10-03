import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {compareClef}=await loadSource('clef-evidence.ts');
const {FrameMonitor}=await loadSource('frame-monitor.ts');
const answers=Object.fromEntries(Object.entries({phase:'player',readability:'clear',player_count:'2',player_1:'A',player_2:'5',dealer_upcard:'2'}).map(([k,value])=>[k,{value,accepted:true}]));
test('independent agreement, mismatch and incomplete evidence stay distinct',()=>{
 const report={player:['A','5'],dealer:['2'],phase:'player'};
 assert.equal(compareClef({answers},report).status,'agreement');
 assert.equal(compareClef({answers},{...report,player:['3','A','5']}).status,'disagreement');
 assert.equal(compareClef({answers:{}},report).status,'inconclusive');
 assert.equal(compareClef({answers:{...answers,player_count:{value:'5',accepted:true}}},{...report,player:['A','5','2','2','2']}).status,'inconclusive');
});
test('frame monitor sees a changed video while duplicate pixels remain stable',()=>{
 const monitor=new FrameMonitor(),a=new Uint8ClampedArray(16).fill(255),b=new Uint8ClampedArray(16).fill(0);
 assert.equal(monitor.observe(a).motion,0);assert.equal(monitor.observe(a).motion,0);
 assert.ok(monitor.observe(b).motion>.9);assert.equal(monitor.observe(b).motion,0);
});
