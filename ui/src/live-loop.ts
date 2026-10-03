type VideoClock={requestVideoFrameCallback?:(callback:(now:number,metadata:{mediaTime:number})=>void)=>number;cancelVideoFrameCallback?:(id:number)=>void;readyState:number;currentTime?:number};
type Heartbeat=(tick:(now:number)=>void,interval:number)=>null|(()=>void);
function workerHeartbeat(tick:(now:number)=>void,interval:number){
 if(typeof Worker!=='function')return null;
 const url=URL.createObjectURL(new Blob(['onmessage=e=>setInterval(()=>postMessage(0),e.data)'],{type:'text/javascript'}));
 try{const worker=new Worker(url);worker.onmessage=()=>tick(performance.now());worker.postMessage(interval);return()=>{worker.terminate();URL.revokeObjectURL(url)}}catch{URL.revokeObjectURL(url);return null}
}
/** One upload in flight. An offscreen clock must still see advancing video time. */
export class LiveVideoLoop{
 private active=false;private pending=false;private id=0;private last=-Infinity;private mediaTime=-Infinity;private generation=0;private cancelHeartbeat:null|(()=>void)=null;
 processed=0;skipped=0;
 constructor(private video:VideoClock,private work:(sequence:number)=>Promise<void>,private onError:(error:unknown)=>void,private interval=350,private heartbeat:Heartbeat=workerHeartbeat){}
 start(){
  this.stop();this.active=true;this.last=-Infinity;this.mediaTime=-Infinity;this.processed=0;this.skipped=0;const generation=this.generation;
  const run=(now:number,mediaTime:number|undefined)=>{
   if(!this.active||generation!==this.generation||this.video.readyState<2||now-this.last<this.interval)return;
   if(typeof mediaTime==='number'&&mediaTime<=this.mediaTime)return;
   if(this.pending){this.skipped++;return}
   this.last=now;if(typeof mediaTime==='number')this.mediaTime=mediaTime;this.pending=true;const sequence=this.processed++;
   void this.work(sequence).catch(error=>{if(this.active&&generation===this.generation)this.onError(error)}).finally(()=>{if(generation===this.generation)this.pending=false});
  };
  const tick=(now:number,mediaTime?:number)=>{
   if(!this.active||generation!==this.generation)return;
   this.schedule(tick);run(now,mediaTime);
  };
  this.schedule(tick);
  this.cancelHeartbeat=this.heartbeat(now=>{const time=this.video.currentTime;if(typeof time==='number'&&Number.isFinite(time))run(now,time)},Math.max(100,Math.min(250,this.interval)));
 }
 private schedule(callback:(now:number,mediaTime?:number)=>void){this.id=this.video.requestVideoFrameCallback?this.video.requestVideoFrameCallback((now,metadata)=>callback(now,metadata.mediaTime)):requestAnimationFrame(now=>callback(now,this.video.currentTime))}
 stop(){this.active=false;this.generation++;this.cancelHeartbeat?.();this.cancelHeartbeat=null;if(this.video.cancelVideoFrameCallback)this.video.cancelVideoFrameCallback(this.id);else if(typeof cancelAnimationFrame==='function')cancelAnimationFrame(this.id);this.pending=false}
}
