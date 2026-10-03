/** Optional local video evidence. Nothing is uploaded or recorded by default. */
export class SessionRecording {
 private recorder:MediaRecorder|null=null;private chunks:Blob[]=[];bytes=0;startedAt=0;
 start(stream:MediaStream,onSaved:(blob:Blob,metadata:any)=>void,onError:(message:string)=>void){
  if(this.recorder)throw new Error('A recording is already active.');
  if(typeof MediaRecorder!=='function')throw new Error('Video recording is unavailable in this browser.');
  const mime=['video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'].find(value=>MediaRecorder.isTypeSupported(value));
  const recorder=new MediaRecorder(stream,mime?{mimeType:mime,videoBitsPerSecond:2000000}:undefined);
  this.chunks=[];this.bytes=0;this.startedAt=performance.now()/1000;this.recorder=recorder;
  recorder.ondataavailable=event=>{if(event.data.size){this.bytes+=event.data.size;this.chunks.push(event.data);if(this.bytes>200*1024*1024){onError('Recording reached 200 MiB and was saved automatically.');this.stop()}}};
  recorder.onerror=()=>{onError('The browser could not record this video.');this.stop()};
  recorder.onstop=()=>{const blob=new Blob(this.chunks,{type:recorder.mimeType||'video/webm'});const metadata={recording_start_timestamp:this.startedAt,recording_end_timestamp:performance.now()/1000,bytes:blob.size,time_basis:'performance.now / 1000, shared with observation timestamps',scope:'Browser-encoded selected video source. Card analysis is sampled separately. Browser capture/encoder drops are not measured.'};this.chunks=[];this.recorder=null;onSaved(blob,metadata)};
  try{recorder.start(1000)}catch(error){this.recorder=null;this.chunks=[];throw error}
 }
 stop(){if(this.recorder?.state==='recording')this.recorder.stop()}
 get active(){return !!this.recorder}
}
export function saveVideo(blob:Blob,name:string){const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
