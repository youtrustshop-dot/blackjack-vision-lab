/** Per-delivered-frame change evidence, separate from card recognition. */
export class FrameMonitor {
 private previous:Uint8Array|null=null;
 frames=0;changed=0;
 observe(rgba:Uint8ClampedArray|Uint8Array){
  const current=new Uint8Array(rgba.length/4);let difference=0;
  for(let i=0;i<current.length;i++){const p=i*4;current[i]=(rgba[p]*77+rgba[p+1]*150+rgba[p+2]*29)>>8;if(this.previous?.length===current.length)difference+=Math.abs(current[i]-this.previous[i])}
  const motion=this.previous?.length===current.length?difference/(current.length*255):0;
  this.previous=current;this.frames++;if(motion>.008)this.changed++;
  return {frames:this.frames,changed:this.changed,motion};
 }
}
