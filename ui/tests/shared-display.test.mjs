import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {SharedDisplay}=await loadSource('shared-display.ts');
function stream(){const track={readyState:'live',stop(){this.readyState='ended'}};return {getTracks:()=>[track],getVideoTracks:()=>[track],clone:()=>stream()}}
function capture(fn){Object.defineProperty(globalThis,'navigator',{configurable:true,value:{mediaDevices:{getDisplayMedia:fn}}})}
test('five tables share one grant but retain independent clone lifetimes',async()=>{
 let grants=0;const root=stream();capture(async()=>{grants++;return root});const pool=new SharedDisplay();
 const clones=await Promise.all(Array.from({length:5},()=>pool.acquire()));
 assert.equal(grants,1);assert.equal(new Set(clones).size,5);
 pool.release(clones[0]);assert.equal(clones[0].getTracks()[0].readyState,'ended');assert.equal(root.getTracks()[0].readyState,'live');
 for(const clone of clones.slice(1))pool.release(clone);
 assert.equal(root.getTracks()[0].readyState,'ended');
});
test('late grant after cancellation is stopped and never attached',async()=>{
 let grant;capture(()=>new Promise(resolve=>grant=resolve));const pool=new SharedDisplay();const request=pool.acquire();
 pool.stop();const selected=stream();grant(selected);await assert.rejects(request,/cancelled/);
 assert.equal(selected.getTracks()[0].readyState,'ended');
});
test('cancelled request cannot clear a newer picker',async()=>{
 const grants=[];capture(()=>new Promise(resolve=>grants.push(resolve)));const pool=new SharedDisplay();
 const old=pool.acquire();pool.stop();const first=pool.acquire(),second=pool.acquire();
 const late=stream();grants[0](late);await assert.rejects(old,/cancelled/);assert.equal(grants.length,2);
 const selected=stream();grants[1](selected);const [a,b]=await Promise.all([first,second]);assert.notEqual(a,b);pool.stop();
 assert.equal(a.getTracks()[0].readyState,'ended');assert.equal(b.getTracks()[0].readyState,'ended');
});
