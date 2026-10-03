import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {LiveVideoLoop}=await loadSource('live-loop.ts');
function clock(){let next=0;const scheduled=new Map();return {readyState:2,requestVideoFrameCallback(fn){scheduled.set(++next,fn);return next},cancelVideoFrameCallback(id){scheduled.delete(id)},tick(now){const [id,fn]=scheduled.entries().next().value;scheduled.delete(id);fn(now,{mediaTime:now/1000})},get scheduled(){return scheduled.size}}}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
test('video loop holds one upload and drops busy observations without queuing',async()=>{
 const video=clock(),calls=[],errors=[];let finish;
 const loop=new LiveVideoLoop(video,seq=>{calls.push(seq);return new Promise(resolve=>finish=resolve)},error=>errors.push(error),100);
 loop.start();video.tick(0);video.tick(110);video.tick(220);
 assert.deepEqual(calls,[0]);assert.equal(loop.skipped,2);
 finish();await flush();video.tick(330);assert.deepEqual(calls,[0,1]);assert.equal(errors.length,0);
 loop.stop();finish();await flush();assert.equal(video.scheduled,0);
});
test('late failure after stop never reaches the current UI',async()=>{
 const video=clock(),errors=[];let reject;
 const loop=new LiveVideoLoop(video,()=>new Promise((_,r)=>reject=r),error=>errors.push(error));
 loop.start();video.tick(0);loop.stop();reject(new Error('stale'));await flush();assert.equal(errors.length,0);
});
test('restart does not let an obsolete promise clear the new in-flight guard',async()=>{
 const video=clock(),finishes=[],calls=[];
 const loop=new LiveVideoLoop(video,seq=>{calls.push(seq);return new Promise(resolve=>finishes.push(resolve))},()=>{},100);
 loop.start();video.tick(0);loop.start();video.tick(110);finishes[0]();await flush();video.tick(220);
 assert.equal(calls.length,2);assert.equal(loop.skipped,1);loop.stop();finishes[1]();await flush();
});
test('unready video does not generate a synthetic observation',()=>{
 const video=clock();video.readyState=0;let called=false;const loop=new LiveVideoLoop(video,async()=>{called=true},()=>{});
 loop.start();video.tick(0);assert.equal(called,false);loop.stop();
});
test('offscreen heartbeat processes advancing video and never renews frozen evidence',async()=>{
 const video=clock();video.currentTime=1;let tick,cancelled=0;const calls=[];
 const loop=new LiveVideoLoop(video,async seq=>{calls.push(seq)},()=>{},100,(fn)=>{tick=fn;return()=>cancelled++});
 loop.start();tick(0);await flush();tick(110);assert.deepEqual(calls,[0]);
 video.currentTime=2;tick(220);await flush();assert.deepEqual(calls,[0,1]);
 loop.stop();video.currentTime=3;tick(330);assert.deepEqual(calls,[0,1]);assert.equal(cancelled,1);
});
