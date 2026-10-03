import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {LiveAnalysis}=await loadSource('live-analysis.ts');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
test('default browser timers preserve the global receiver',async()=>{
 const schedule=globalThis.setTimeout,cancel=globalThis.clearTimeout;let checks=0;
 globalThis.setTimeout=function(...args){assert.equal(this,globalThis);checks++;return schedule(...args)};
 globalThis.clearTimeout=function(...args){assert.equal(this,globalThis);checks++;return cancel(...args)};
 try{const poller=new LiveAnalysis();poller.watch('default',async()=>({analysis:{status:'complete'}}),()=>{});await flush();poller.stop();assert.ok(checks>=2)}
 finally{globalThis.setTimeout=schedule;globalThis.clearTimeout=cancel}
});
function timers(){let next=0;const pending=new Map();return {schedule(fn,ms){pending.set(++next,{fn,ms});return next},cancel(id){pending.delete(id)},tick(ms){const item=[...pending.entries()].find(([,x])=>x.ms===ms);if(item){pending.delete(item[0]);item[1].fn()}},get size(){return pending.size}}}
test('slow EV does not delay the base response and an old state cannot publish',async()=>{
 const clock=timers(),poller=new LiveAnalysis(clock.schedule,clock.cancel),shown=[];let finish;
 poller.watch('round1',()=>new Promise(resolve=>finish=resolve),value=>shown.push(value));
 // The caller can show its base result immediately, without awaiting watch.
 shown.push({base:'stand'});
 poller.watch('round2',async()=>({analysis:{status:'complete'},action:'hit'}),value=>shown.push(value));
 await flush();finish({analysis:{status:'complete'},action:'stand'});await flush();
 assert.deepEqual(shown,[{base:'stand'},{analysis:{status:'complete'},action:'hit'}]);
 assert.equal(clock.size,0);poller.stop();
});
test('one poll in flight, same-state frames do not queue extra requests',async()=>{
 const clock=timers(),poller=new LiveAnalysis(clock.schedule,clock.cancel);let calls=0,finish;
 const load=()=>{calls++;return new Promise(resolve=>finish=resolve)};
 for(let i=0;i<20;i++)poller.watch('same',load,()=>{});
 assert.equal(calls,1);finish({analysis:{status:'pending'}});await flush();clock.tick(150);assert.equal(calls,2);poller.stop();finish({analysis:{status:'complete'}});await flush();assert.equal(clock.size,0);
});
test('motion/stop invalidates even a fetcher that ignores abort',async()=>{
 const clock=timers(),poller=new LiveAnalysis(clock.schedule,clock.cancel),shown=[];let finish,signal;
 poller.watch('motion0',s=>{signal=s;return new Promise(resolve=>finish=resolve)},value=>shown.push(value));
 poller.stop();assert.ok(signal.aborted);finish({analysis:{status:'complete'}});await flush();assert.deepEqual(shown,[]);assert.equal(clock.size,0);
});
test('EV failure leaves the base result untouched',async()=>{
 const clock=timers(),poller=new LiveAnalysis(clock.schedule,clock.cancel),shown=[{base:'double'}];
 poller.watch('same',async()=>{throw new Error('deadline')},value=>shown.push(value));await flush();assert.deepEqual(shown,[{base:'double'}]);assert.equal(clock.size,0);poller.stop();
});
test('pending polling has a finite attempt budget',async()=>{
 const clock=timers(),poller=new LiveAnalysis(clock.schedule,clock.cancel);let calls=0;
 poller.watch('same',async()=>{calls++;return {analysis:{status:'pending'}}},()=>{});
 for(let i=0;i<30;i++){await flush();clock.tick(150)}await flush();assert.equal(calls,20);assert.equal(clock.size,0);poller.stop();
});
