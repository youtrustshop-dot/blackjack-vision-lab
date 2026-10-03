import {useEffect,useRef,useState} from 'react';
import {api} from './api';
import {compareClef,VisualEvidence} from './clef-evidence';
import {localize} from './localize';

/** One independent verification in flight; obsolete answers cannot label a new hand. */
export function useClefVerification(evidence:VisualEvidence|null,enabled:boolean){
 const latest=useRef(evidence),alive=useRef(true),pending=useRef(false),completed=useRef('');
 const [result,setResult]=useState<any>(null),[busy,setBusy]=useState(false),[tick,setTick]=useState(0);
 latest.current=enabled?evidence:null;
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;latest.current=null}},[]);
 useEffect(()=>{
  if(!enabled||!evidence){setResult(null);return}
  setResult((current:any)=>current?.key===evidence.key?current:null);
  if(pending.current||completed.current===evidence.key)return;
  const captured=evidence;pending.current=true;setBusy(true);
  void api('/models/clef/verify',{image_base64:captured.image,task:'table',corners:captured.corners,output_height:captured.output_height}).then(value=>{
   if(alive.current&&latest.current?.key===captured.key){completed.current=captured.key;setResult({...value,key:captured.key,comparison:compareClef(value,captured.report)})}
  }).catch(error=>{if(alive.current&&latest.current?.key===captured.key){completed.current=captured.key;setResult({key:captured.key,error:error instanceof Error?error.message:String(error)})}}).finally(()=>{pending.current=false;if(alive.current){setBusy(false);setTick(n=>n+1)}});
 },[evidence?.key,enabled,tick]);
 return {result:result?.key===evidence?.key&&enabled?result:null,busy};
}
export default function ClefVerification({result,busy}:{result:any;busy:boolean}){
 return localize(<div className="clef-verification" role="status"><strong>{busy?'Clef is checking the captured table…':result?.comparison?.status==='agreement'?'Clef agrees with the visible hand':result?.comparison?.status==='disagreement'?'Visual disagreement — confirm the cards':result?.error?'Clef unavailable':result?'Clef verification inconclusive':'Independent Clef verification'}</strong><p>{result?.error||result?.comparison?.issues?.[0]||'Experimental second check. Model scores are not recognition accuracy or outcome probabilities.'}</p>{result?.latency_ms!==undefined&&<small>{Math.round(result.latency_ms)} ms · local model</small>}<details><summary>Inspect visual evidence</summary><pre>{result?JSON.stringify(result,null,2):'Start the separate local Clef runtime on port 9051.'}</pre></details></div>);
}
