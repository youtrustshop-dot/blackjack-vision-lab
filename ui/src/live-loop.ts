type VideoClock={requestVideoFrameCallback?:(callback:(now:number,metadata:{mediaTime:number})=>void)=>number;cancelVideoFrameCallback?:(id:number)=>void;readyState:number};
/** One in-flight upload. Later video observations replace work, never queue it. */
export class LiveVideoLoop{
 private active=false;private pending=false;private id=0;private last=-Infinity;private generation=0;
 processed=0;skipped=0;
 constructor(private video:VideoClock,private work:(sequence:number)=>Promise<void>,private onError:(error:unknown)=>void,private interval=350){}
 start(){this.stop();this.active=true;this.last=-Infinity;this.processed=0;this.skipped=0;const generation=this.generation;
  const tick=(now:number)=>{
   if(!this.active||generation!==this.generation)return;
   this.schedule(tick);
   if(this.video.readyState<2||now-this.last<this.interval)return;
   if(this.pending){this.skipped++;return}
   this.last=now;this.pending=true;const sequence=this.processed++;
   void this.work(sequence).catch(error=>{if(this.active&&generation===this.generation)this.onError(error)}).finally(()=>{if(generation===this.generation)this.pending=false});
  };this.schedule(tick);
 }
 private schedule(callback:(now:number)=>void){this.id=this.video.requestVideoFrameCallback?this.video.requestVideoFrameCallback(now=>callback(now)):requestAnimationFrame(callback)}
 stop(){this.active=false;this.generation++;if(this.video.cancelVideoFrameCallback)this.video.cancelVideoFrameCallback(this.id);else if(typeof cancelAnimationFrame==='function')cancelAnimationFrame(this.id);this.pending=false}
}
