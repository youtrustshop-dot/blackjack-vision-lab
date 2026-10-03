import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {ScreenShare,screenSharingError,captureScreenFrame}=await loadSource('screen-sharing.ts');
function source(){const tracks=[{stops:0,stop(){this.stops++}},{stops:0,stop(){this.stops++}}];return {tracks,getTracks:()=>tracks}}

test('display access is lazy and all owned tracks stop',async()=>{
 const stream=source();let calls=0;const owner=new ScreenShare(async()=>{calls++;return stream});
 assert.equal(calls,0);assert.equal(await owner.start(),stream);assert.equal(calls,1);
 owner.stop();owner.stop();assert.deepEqual(stream.tracks.map(t=>t.stops),[1,1]);
});
test('cancelling a pending chooser stops any stream granted later',async()=>{
 const stream=source();let grant;const owner=new ScreenShare(()=>new Promise(resolve=>{grant=resolve}));
 const pending=owner.start();owner.stop();grant(stream);assert.equal(await pending,null);
 assert.deepEqual(stream.tracks.map(t=>t.stops),[1,1]);
});
test('a superseded request cannot replace or stop the newer source',async()=>{
 const old=source(),current=source();let grant;let calls=0;
 const owner=new ScreenShare(()=>++calls===1?new Promise(resolve=>{grant=resolve}):Promise.resolve(current));
 const pending=owner.start();assert.equal(await owner.start(),current);grant(old);assert.equal(await pending,null);
 assert.deepEqual(old.tracks.map(t=>t.stops),[1,1]);assert.deepEqual(current.tracks.map(t=>t.stops),[0,0]);
 owner.stop();assert.deepEqual(current.tracks.map(t=>t.stops),[1,1]);
});
test('denial leaves no active stream and supports a fresh request',async()=>{
 const stream=source();let calls=0;const owner=new ScreenShare(async()=>{if(++calls===1)throw new DOMException('Denied','NotAllowedError');return stream});
 await assert.rejects(owner.start(),{name:'NotAllowedError'});
 assert.match(screenSharingError(new DOMException('Denied','NotAllowedError')),/annullata o non autorizzata/);
 assert.equal(await owner.start(),stream);owner.stop();
});
test('a frame is unavailable until the video has real pixel dimensions',async()=>{
 await assert.rejects(captureScreenFrame({readyState:1,videoWidth:0,videoHeight:0}),/anteprima/);
});
