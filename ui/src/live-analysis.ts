/** One bounded poller; old source/state/motion generations cannot publish. */
export class LiveAnalysis {
 private key:string|null=null;
 private epoch=0;
 private controller:AbortController|null=null;
 private timer:ReturnType<typeof setTimeout>|null=null;
 constructor(private schedule=(fn:()=>void,ms:number)=>globalThis.setTimeout(fn,ms),
             private cancel=(id:ReturnType<typeof setTimeout>)=>globalThis.clearTimeout(id)){}
 stop(){this.epoch++;this.key=null;this.controller?.abort();this.controller=null;if(this.timer!==null)this.cancel(this.timer);this.timer=null}
 watch(key:string,load:(signal:AbortSignal)=>Promise<any>,publish:(value:any)=>void){
  if(key===this.key)return;
  this.stop();this.key=key;const epoch=this.epoch;let attempts=0;
  const poll=async()=>{
   if(epoch!==this.epoch)return;
   const controller=new AbortController();this.controller=controller;
   const deadline=this.schedule(()=>controller.abort(),1500);
   try{
    const value=await load(controller.signal);
    if(epoch!==this.epoch||controller.signal.aborted)return;
    publish(value);
    if(['ready','pending','busy'].includes(value.analysis?.status)&&++attempts<20)
     this.timer=this.schedule(()=>void poll(),150);
   }catch{/* Keep the usable base action; never clear it for an EV failure. */}
   finally{this.cancel(deadline);if(this.controller===controller)this.controller=null}
  };
  void poll();
 }
}
