import {api,fetchApi,Rules,Snapshot} from './api';

/** A real MediaStream of an independently rendered, visible simulation. */
export class DemoVideoSource{
 private canvas=document.createElement('canvas');private stream:MediaStream|null=null;private state:Snapshot|null=null;
 private image:ImageBitmap|null=null;private timer=0;private botTimer=0;private disposed=false;private bot=true;private busy=false;
 constructor(private rules:Rules,private onState:(state:Snapshot)=>void){}
 async start(){
  this.state=await api<Snapshot>('/sessions',{rules:this.rules,seed:42});
  if(this.disposed){void this.removeSession();throw new Error('Demo cancelled.')}
  this.state=await api<Snapshot>('/sessions/'+this.state.session_id+'/deal',{});
  await this.render();
  if(this.disposed)throw new Error('Demo cancelled.');
  this.stream=this.canvas.captureStream(15);
  this.timer=window.setInterval(()=>{if(this.image)this.canvas.getContext('2d')?.drawImage(this.image,0,0)},66);
  this.botTimer=window.setInterval(()=>{if(this.bot)void this.step()},4000);
  return this.stream;
 }
 setBot(value:boolean){this.bot=value}
 async action(action:string){if(this.busy||!this.state||this.disposed)return;this.busy=true;try{
  this.state=await api<Snapshot>('/sessions/'+this.state.session_id+(action==='deal'?'/deal':'/action'),action==='deal'?{}:{action});await this.render();
 }finally{this.busy=false}}
 private async step(){if(this.busy||!this.state||this.disposed)return;this.busy=true;try{
  this.state=await api<Snapshot>('/sessions/'+this.state.session_id+'/bot-step',{});await this.render();
 }catch{/* The observer reports transport failures; leave the last visible table. */}finally{this.busy=false}}
 private async render(){if(!this.state||this.disposed)return;
  const response=await fetchApi('/sessions/'+this.state.session_id+'/frame?live_context=true&v='+Date.now());
  if(!response.ok)throw new Error('Could not render the simulation.');
  const next=await createImageBitmap(await response.blob());
  if(this.disposed){next.close();return}
  this.image?.close();this.image=next;this.canvas.width=next.width;this.canvas.height=next.height;
  this.canvas.getContext('2d')?.drawImage(next,0,0);this.onState(this.state);
 }
 private async removeSession(){if(this.state)await fetchApi('/sessions/'+this.state.session_id,{method:'DELETE'}).catch(()=>{})}
 dispose(){this.disposed=true;clearInterval(this.timer);clearInterval(this.botTimer);this.stream?.getTracks().forEach(t=>t.stop());this.image?.close();void this.removeSession()}
}
