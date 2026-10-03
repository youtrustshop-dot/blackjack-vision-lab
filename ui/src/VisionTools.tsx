import {localize} from './localize';
import {useEffect,useRef,useState} from 'react';
import {Check,Download,Eye,RotateCcw,Upload} from 'lucide-react';
import {api,download,fetchApi} from './api';

type Props={sid?:string;budget:number;onResult:(value:any)=>void;canAnalyze:boolean;observation:unknown;connected:boolean};
const show=(value:unknown)=>JSON.stringify(value,null,2);
const initialZones='{"dealer":[0,0,960,250],"player:0":[0,250,960,350]}';
const ranks=['A','2','3','4','5','6','7','8','9','10','J','Q','K'];
export default function VisionTools({sid,budget,onResult,canAnalyze,observation,connected}:Props){
 const [open,setOpen]=useState(false),[file,setFile]=useState<File|null>(null),[url,setUrl]=useState(''),[corners,setCorners]=useState<number[][]>([]),[zones,setZones]=useState(initialZones);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[observed,setObserved]=useState<any>(null),[stride,setStride]=useState(3),[maxFrames,setMaxFrames]=useState(120);
 const [cardId,setCardId]=useState(''),[rank,setRank]=useState('A'),[suit,setSuit]=useState('S'),[reason,setReason]=useState('');
 const videoRef=useRef<HTMLInputElement>(null);
 const [attachSession,setAttachSession]=useState(false),[declaredDecks,setDeclaredDecks]=useState('');
 useEffect(()=>{if(!file){setUrl('');return}const next=URL.createObjectURL(file);setUrl(next);setCorners([]);return()=>URL.revokeObjectURL(next)},[file]);
 useEffect(()=>{setObserved(null);setError('')},[sid]);
 useEffect(()=>{setObserved(null)},[observation]);
 const run=async(fn:()=>Promise<void>)=>{setError('');setBusy(true);try{await fn()}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
 const importImage=()=>run(async()=>{
  if(!file)throw new Error('Seleziona un’immagine.');
  if(corners.length!==0&&corners.length!==4)throw new Error('Indica tutti i quattro angoli oppure azzera la selezione.');
  const zoneMap=JSON.parse(zones);
  const encoded=await new Promise<string>((resolve,reject)=>{const r=new FileReader();r.onerror=()=>reject(new Error('Lettura del file non riuscita.'));r.onload=()=>resolve(String(r.result).split(',')[1]);r.readAsDataURL(file)});
  onResult(await api('/vision/upload',{image_base64:encoded,session_id:attachSession?sid:undefined,decks:declaredDecks?Number(declaredDecks):undefined,frames:3,corners:corners.length===4?corners:undefined,corners_normalized:true,zones:zoneMap,output_width:960,output_height:600}));
 });
 const importVideo=(video:File)=>run(async()=>{
  if(video.size>64*1024*1024)throw new Error('Il video supera 64 MiB.');
  const response=await fetchApi('/vision/upload-video?stride='+stride+'&max_frames='+maxFrames+(declaredDecks?'&decks='+declaredDecks:''),{method:'POST',body:video,headers:{'Content-Type':video.type||'application/octet-stream'}});
  const value=await response.json();
  if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:show(value.detail));
  onResult(value);
 });
 const analyze=()=>run(async()=>{if(sid)setObserved(await api('/sessions/'+sid+'/perception/analyze',{timeout_ms:budget}))});
 const correct=()=>run(async()=>{if(sid)onResult(await api('/sessions/'+sid+'/perception/correct',{card_id:cardId,rank,suit,reason}))});
 return localize(<section className="panel vision-tools">
  <div className="panel-header"><h2>Calibrazione, video e stato osservato</h2><button className="text-button" onClick={()=>setOpen(v=>!v)} aria-expanded={open}>{open?'Chiudi strumenti':'Apri strumenti'}</button></div>
  <div className="observed-controls"><button className="button primary" disabled={busy||!sid||!canAnalyze||!connected} onClick={analyze}><Eye size={15}/>EV dalla percezione</button><span>{canAnalyze?'Il gate verifica lo stato ricostruito prima del calcolo.':'Questo import è indipendente. Analizza il frame del simulatore o associa esplicitamente un’immagine alla sessione.'}</span></div>
  {error&&<p className="tool-error" role="alert">{error}</p>}
  {observed&&<div className="observed-result"><div className="section-label">{observed.status==='gated'?'ANALISI BLOCCATA DAL GATE':'RISULTATO DELLO STATO OSSERVATO'}</div><pre>{show(observed)}</pre><button className="button secondary" onClick={()=>download('observed-analysis.json',observed)}><Download size={14}/>Esporta analisi</button></div>}
  {open&&<><div className="import-context"><label>Mazzi dichiarati per l’import<select aria-label="Mazzi dichiarati per l’import" value={declaredDecks} onChange={e=>setDeclaredDecks(e.target.value)}><option value="">Sconosciuti</option>{[1,2,4,6,8].map(d=><option key={d} value={d}>{d}</option>)}</select></label><label><input type="checkbox" checked={attachSession} onChange={e=>setAttachSession(e.target.checked)}/>Associa l’immagine al tracker della sessione attiva</label><p>La configurazione dichiarata non dimostra che lo shoe sia stato osservato dall’inizio. Importa clip di un singolo round.</p></div><div className="tool-grid">
   <div><h3>Normalizza un’immagine</h3><p>Seleziona gli angoli in ordine: alto sinistra, alto destra, basso destra, basso sinistra. Le zone sono rettangoli [x, y, larghezza, altezza] sul frame 960 × 600.</p>
    <label className="file-picker">Immagine da calibrare<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>setFile(e.target.files?.[0]||null)}/></label>
    {url&&<div className="calibration-preview" onClick={e=>{if(corners.length===4)return;const b=e.currentTarget.getBoundingClientRect();setCorners(v=>[...v,[(e.clientX-b.left)/b.width,(e.clientY-b.top)/b.height]])}}><img src={url} alt="Immagine: seleziona i quattro angoli del tavolo"/>{corners.map((c,i)=><span key={i} style={{left:c[0]*100+'%',top:c[1]*100+'%'}}>{i+1}</span>)}</div>}
    <div className="calibration-status"><span>{corners.length} / 4 angoli</span><button className="button secondary" onClick={()=>setCorners([])}><RotateCcw size={12}/>Azzera</button></div>
    <label>Zone di riconoscimento<textarea aria-label="Zone di riconoscimento" value={zones} onChange={e=>setZones(e.target.value)}/></label>
    <button className="button secondary" disabled={busy||!file||!connected} onClick={importImage}><Upload size={14}/>Calibra e importa</button>
   </div>
   <div><h3>Analizza un video locale</h3><p>La ricostruzione usa i frame decodificati. Il report distingue le carte stabili dalle osservazioni ambigue.</p>
    <div className="compact-form"><label>Un frame ogni<input type="number" min="1" max="120" value={stride} onChange={e=>setStride(Number(e.target.value))}/></label><label>Massimo frame<input type="number" min="1" max="600" value={maxFrames} onChange={e=>setMaxFrames(Number(e.target.value))}/></label></div>
    <button className="button secondary" disabled={busy||!connected} onClick={()=>videoRef.current?.click()}><Upload size={14}/>Carica video</button><input hidden ref={videoRef} type="file" accept="video/*" onChange={e=>e.target.files?.[0]&&void importVideo(e.target.files[0])}/>
    <h3>Correggi una carta osservata</h3><p>Usa l’identità logica riportata nello stato. La correzione viene aggiunta al registro con la tua motivazione.</p>
    <div className="compact-form"><label>ID logico<input aria-label="ID logico" value={cardId} onChange={e=>setCardId(e.target.value)}/></label><label>Valore<select value={rank} onChange={e=>setRank(e.target.value)}>{ranks.map(r=><option key={r}>{r}</option>)}</select></label><label>Seme<select value={suit} onChange={e=>setSuit(e.target.value)}>{['S','H','D','C'].map(s=><option key={s}>{s}</option>)}</select></label></div>
    <label>Motivazione<input aria-label="Motivazione della correzione" value={reason} onChange={e=>setReason(e.target.value)}/></label>
    <button className="button secondary" disabled={busy||!sid||!cardId||reason.length<3||!connected} onClick={correct}><Check size={14}/>Registra correzione</button>
   </div>
  </div></>}
 </section>);
}
