/** One user-selected display; each table owns its clone and its observer state. */
export class SharedDisplay{
 private source:MediaStream|null=null;private pending:Promise<MediaStream>|null=null;private clones=new Set<MediaStream>();private generation=0;
 async acquire():Promise<MediaStream>{
  if(!this.source?.getVideoTracks().some(t=>t.readyState==='live')){
   if(!navigator.mediaDevices?.getDisplayMedia)throw new Error('Open this local app in Chrome or Edge to share a display.');
   const generation=this.generation;
   if(!this.pending)this.pending=navigator.mediaDevices.getDisplayMedia({video:{frameRate:{ideal:15,max:30}},audio:false});
   const pending=this.pending;
   try{const selected=await pending;if(generation!==this.generation){selected.getTracks().forEach(t=>t.stop());throw new Error('Display sharing was cancelled.')}this.source=selected}finally{if(this.pending===pending)this.pending=null}
  }
  const clone=this.source!.clone();this.clones.add(clone);return clone;
 }
 release(stream:MediaStream){this.clones.delete(stream);stream.getTracks().forEach(t=>t.stop());if(!this.clones.size){this.source?.getTracks().forEach(t=>t.stop());this.source=null}}
 stop(){this.generation++;this.pending=null;for(const clone of this.clones)clone.getTracks().forEach(t=>t.stop());this.clones.clear();this.source?.getTracks().forEach(t=>t.stop());this.source=null}
}
