import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {SessionRecording}=await loadSource('session-recording.ts');
test('local recording starts explicitly and preserves a completed video with metadata',()=>{
 let recorder,saved;
 const previous=globalThis.MediaRecorder;
 globalThis.MediaRecorder=class{
  static isTypeSupported(){return true}
  constructor(stream,options){recorder=this;this.mimeType=options.mimeType;this.state='inactive';assert.equal(stream,'selected-source')}
  start(interval){assert.equal(interval,1000);this.state='recording'}
  stop(){this.state='inactive';this.onstop()}
 };
 try{
  const recording=new SessionRecording();assert.equal(recording.active,false);
  recording.start('selected-source',(blob,metadata)=>{saved={blob,metadata}},()=>assert.fail());
  assert.equal(recording.active,true);
  recorder.ondataavailable({data:new Blob(['encoded video'])});recording.stop();
  assert.equal(recording.active,false);assert.equal(saved.blob.size,13);
  assert.equal(saved.metadata.bytes,13);assert.ok(saved.metadata.recording_end_timestamp>=saved.metadata.recording_start_timestamp);
 }finally{globalThis.MediaRecorder=previous}
});
test('failed browser recording start releases the recorder state',()=>{
 const previous=globalThis.MediaRecorder;
 globalThis.MediaRecorder=class{static isTypeSupported(){return true}start(){throw Error('encoder unavailable')}};
 try{const recording=new SessionRecording();assert.throws(()=>recording.start({},()=>{},()=>{}));assert.equal(recording.active,false)}
 finally{globalThis.MediaRecorder=previous}
});
