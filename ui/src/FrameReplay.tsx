import {useEffect,useState} from 'react';
import {ChevronLeft,ChevronRight} from 'lucide-react';
const show=(value:unknown)=>JSON.stringify(value,null,2);
export default function FrameReplay({result}:{result:any}){
 const [cursor,setCursor]=useState(0);
 const frames=Array.isArray(result?.frames)?result.frames:[];
 useEffect(()=>{setCursor(0)},[result]);
 if(!frames.length)return null;
 const frame=frames[Math.min(cursor,frames.length-1)];
 const events=Array.isArray(result.events)?result.events.slice(0,(frame.event_end_index??-1)+1):[];
 return <section className="panel frame-replay" aria-label="Replay dei frame video">
  <div className="panel-header"><h2>Replay dei frame</h2><small>Clip di un singolo round · frame campionati</small></div>
  <div className="timeline-controls"><button className="icon-button" title="Frame precedente" disabled={cursor===0} onClick={()=>setCursor(c=>c-1)}><ChevronLeft size={15}/></button><input aria-label="Posizione frame video" type="range" min="0" max={frames.length-1} value={cursor} onChange={e=>setCursor(Number(e.target.value))}/><button className="icon-button" title="Frame successivo" disabled={cursor===frames.length-1} onClick={()=>setCursor(c=>c+1)}><ChevronRight size={15}/></button><b>{cursor+1} / {frames.length}</b></div>
  <div className="frame-replay-body"><div><p>Frame sorgente {frame.frame_index??frame.frame} · {typeof frame.timestamp==='number'?frame.timestamp.toFixed(3):'—'} s</p>
   {frame.image_base64?<div className="video-frame-wrap"><img src={'data:'+(frame.image_format||'image/jpeg')+';base64,'+frame.image_base64} alt={'Frame video '+(frame.frame_index??frame.frame)}/><svg className="detection-overlay" viewBox={'0 0 '+frame.frame_width+' '+frame.frame_height} aria-label="Bounding box del frame video">{(frame.detections||[]).map((d:any,i:number)=>{const [x,y,w,h]=d.bbox||[];return <rect key={i} x={x} y={y} width={w} height={h}/>})}</svg></div>:<p>Anteprima non inclusa nel report.</p>}
  </div><div><details open><summary>Stato fino a questo frame</summary><pre>{show(frame.replay_state)}</pre></details><details><summary>Eventi fino a questo frame ({events.length})</summary><pre>{show(events)}</pre></details><details><summary>Detections del frame</summary><pre>{show(frame.detections)}</pre></details></div></div>
 </section>;
}
