import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../../extensions/chromium/capture.js',import.meta.url),'utf8');
const {localAddress,captureSelectedTab}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('extension analysis destinations are restricted to plain HTTP loopback',()=>{
 assert.equal(localAddress('http://127.0.0.1:8767/'),'http://127.0.0.1:8767');
 assert.equal(localAddress('http://localhost:8765'),'http://localhost:8765');
 for(const value of ['https://example.com','http://127.0.0.1.evil.test','file:///tmp','http://user:secret@localhost'])assert.throws(()=>localAddress(value));
});
test('tab capture rejects a changed active tab before returning any image',async()=>{
 let query=0;await assert.rejects(captureSelectedTab({query:async()=>[{id:++query,windowId:2}],captureVisibleTab:async()=> 'pixels'}),/changed/);
 const options=[];assert.equal(await captureSelectedTab({query:async()=>[{id:1,windowId:2}],captureVisibleTab:async(...args)=>{options.push(args);return 'image'}}),'image');
 assert.deepEqual(options,[[2,{format:'png'}]]);
});
