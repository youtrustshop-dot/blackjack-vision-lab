import {localize} from './localize';
import {useEffect,useState} from 'react';
import {ChevronLeft,ChevronRight} from 'lucide-react';
import {parseCorrection,readCorrections,differences,type Correction} from './replayCorrections';
const show=(value:unknown)=>JSON.stringify(value,null,2);
export default function FrameReplay({result}:{result:any}){
 const [cursor,setCursor]=useState(0);
 const [identity,setIdentity]=useState(''),[corrections,setCorrections]=useState<Correction[]>([]),[draft,setDraft]=useState(''),[note,setNote]=useState(''),[error,setError]=useState(''),[historyError,setHistoryError]=useState(''),[loaded,setLoaded]=useState(false);
 const frames=Array.isArray(result?.frames)?result.frames:[];
 useEffect(()=>{setCursor(0)},[result]);
 useEffect(()=>{let cancelled=false;setIdentity('');setCorrections([]);setError('');setHistoryError('');setLoaded(false);
  void crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(result))).then(hash=>{
   if(cancelled)return;const id=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');setIdentity(id);
   try{setCorrections(readCorrections(localStorage.getItem('vision-replay:'+id)));setLoaded(true)}catch(e){setHistoryError(String(e))}
  }).catch(e=>{if(!cancelled)setError(String(e))});return()=>{cancelled=true};
 },[result]);
 useEffect(()=>{setDraft(show(frames[cursor]?.replay_state??{}));setNote('');setError('')},[cursor,result]);
 if(!frames.length)return null;
 const frame=frames[Math.min(cursor,frames.length-1)];
 const events=Array.isArray(result.events)?result.events.slice(0,(frame.event_end_index??-1)+1):[];
 const correction=corrections.filter(c=>c.frame===cursor).at(-1);
 const save=()=>{try{if(!identity||!loaded)throw new Error('Report or correction history not ready');const current=readCorrections(localStorage.getItem('vision-replay:'+identity));if(current.length>=500)throw new Error('Maximum 500 correction revisions per report');
  const next=[...current,{frame:cursor,original:frame.replay_state??{},corrected:parseCorrection(draft),note:note.slice(0,2000),createdAt:Date.now()}];
  const encoded=JSON.stringify(next);if(encoded.length>5_000_000)throw new Error('Correction history exceeds the local limit');localStorage.setItem('vision-replay:'+identity,encoded);setCorrections(next);setError('');
 }catch(e){setError(String(e))}};
 return localize(<section className="panel frame-replay" aria-label="Replay dei frame video">
  <div className="panel-header"><h2>Replay dei frame</h2><small>Clip di un singolo round · frame campionati</small></div>
  <div className="timeline-controls"><button className="icon-button" title="Frame precedente" disabled={cursor===0} onClick={()=>setCursor(c=>c-1)}><ChevronLeft size={15}/></button><input aria-label="Posizione frame video" type="range" min="0" max={frames.length-1} value={cursor} onChange={e=>setCursor(Number(e.target.value))}/><button className="icon-button" title="Frame successivo" disabled={cursor===frames.length-1} onClick={()=>setCursor(c=>c+1)}><ChevronRight size={15}/></button><b>{cursor+1} / {frames.length}</b></div>
  <div className="frame-replay-body"><div><p>Frame sorgente {frame.frame_index??frame.frame} · {typeof frame.timestamp==='number'?frame.timestamp.toFixed(3):'—'} s</p>
   {frame.image_base64?<div className="video-frame-wrap"><img src={'data:'+(frame.image_format||'image/jpeg')+';base64,'+frame.image_base64} alt={'Frame video '+(frame.frame_index??frame.frame)}/><svg className="detection-overlay" viewBox={'0 0 '+frame.frame_width+' '+frame.frame_height} aria-label="Bounding box del frame video">{(frame.detections||[]).map((d:any,i:number)=>{const [x,y,w,h]=d.bbox||[];return localize(<rect key={i} x={x} y={y} width={w} height={h}/>)})}</svg></div>:<p>Anteprima non inclusa nel report.</p>}
  </div><div><details open><summary>Stato fino a questo frame</summary><pre>{show(frame.replay_state)}</pre></details><details><summary>Eventi fino a questo frame ({events.length})</summary><pre>{show(events)}</pre></details><details><summary>Detections del frame</summary><pre>{show(frame.detections)}</pre></details></div></div>
 <details><summary>Manual correction · original report retained</summary><p>Report SHA-256: {identity||'calculating'}. Local revisions do not retrain a detector or change recognized events.</p><label>Corrected observation (JSON object)<textarea rows={8} maxLength={30000} value={draft} onChange={e=>setDraft(e.target.value)}/></label><label>Evidence / reason<textarea rows={2} maxLength={2000} value={note} onChange={e=>setNote(e.target.value)}/></label><button className="button secondary" disabled={!identity||!loaded} onClick={save}>Save correction revision</button>{(historyError||error)&&<p role="alert">{historyError||error}</p>}{correction&&<><h3>Differences from original observation</h3><pre>{show(differences(frame.replay_state,correction.corrected))}</pre><p>{corrections.filter(c=>c.frame===cursor).length} retained revisions · {correction.note}</p></>}</details>
 </section>);
}
