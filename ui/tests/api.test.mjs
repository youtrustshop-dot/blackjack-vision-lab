import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {api,fetchApi,BackendConnectionError,ApiResponseError}=await loadSource('api.ts');

test('transport loss gives a recovery message and notifies the application',async t=>{
 const events=[];t.mock.method(globalThis,'fetch',async()=>{throw new TypeError('Failed to fetch')});
 const previous=globalThis.window;globalThis.window={dispatchEvent:event=>events.push(event.type)};
 try{await assert.rejects(api('/health'),error=>error instanceof BackendConnectionError&&error.message.includes('run.ps1'));assert.deepEqual(events,['bjlab:backend-unavailable'])}
 finally{if(previous===undefined)delete globalThis.window;else globalThis.window=previous}
});
test('an expired session is a 404, so reconnect can create a new session',async t=>{
 t.mock.method(globalThis,'fetch',async()=>new Response(JSON.stringify({detail:'Session not found'}),{status:404}));
 await assert.rejects(api('/sessions/old'),error=>error instanceof ApiResponseError&&error.status===404&&error.message==='Session not found');
});
test('aborting an obsolete request does not report a backend outage',async t=>{
 const error=new DOMException('Aborted','AbortError');t.mock.method(globalThis,'fetch',async()=>{throw error});
 await assert.rejects(fetchApi('/health'),value=>value===error);
});
test('non-JSON responses cannot masquerade as a session',async t=>{
 t.mock.method(globalThis,'fetch',async()=>new Response('<html>wrong service</html>',{status:200}));
 await assert.rejects(api('/health'),error=>error instanceof ApiResponseError&&error.message.includes('non valida'));
});
