import {useEffect,useState} from 'react';
import {api} from './api';
import {LiveAdvisor} from './LiveVision';
import {nativeControl} from './native-advisor';
import {evidenceExpiry} from './advisor-evidence';
import {localize} from './localize';

export default function NativeAdvisor(){
 const stream=new URLSearchParams(location.search).get('advisor')!;
 const [status,setStatus]=useState<any>(null),[value,setValue]=useState<any>(null),[expires,setExpires]=useState(0),[now,setNow]=useState(performance.now()),[error,setError]=useState('');
 useEffect(()=>{let active=true,timer:ReturnType<typeof setTimeout>;
  const poll=async()=>{const began=performance.now();try{
   const [state,host]=await Promise.all([api('/native/advisor/'+stream+'/state'),api('/native/advisor/status')]);
   if(active){setValue(state);setStatus(host);setExpires(evidenceExpiry(state.evidence_ttl_ms,began,performance.now()));setError('')}
  }catch(e){if(active){setValue(null);setExpires(0);setError(e instanceof Error?e.message:String(e))}}
  finally{if(active)timer=setTimeout(poll,350)}};void poll();const tick=setInterval(()=>setNow(performance.now()),150);
  return()=>{active=false;clearTimeout(timer);clearInterval(tick)};
 },[stream]);
 const action=async(operation:'hide'|'topmost',topmost?:boolean)=>{try{await nativeControl(operation,undefined,undefined,topmost)}catch(e){setError(e instanceof Error?e.message:String(e))}};
 return localize(<main className="external-advisor"><header className="external-advisor-toolbar"><span>{status?.table_name||'Live advisor'}</span><label><input type="checkbox" checked={status?.topmost||false} onChange={e=>void action('topmost',e.target.checked)}/>Always on top</label><button className="text-button" onClick={()=>void action('hide')}>Close</button></header>{status?.tables?.length>1&&<select aria-label="Selected table" value={stream} onChange={e=>{const table=status.tables.find((t:any)=>t.stream_id===e.target.value);void nativeControl('open',table.stream_id,table.table_name)}}>{status.tables.map((table:any)=><option key={table.stream_id} value={table.stream_id}>{table.table_name}</option>)}</select>}{error&&<p role="alert">{error}</p>}<LiveAdvisor report={value?.report} stale={!value||value.stale||now>=expires} compact/><p className="panel-caption">Drag the native title bar to another monitor. This window views one observer; closing it keeps capture active.</p>{value?.evidence_timestamp&&<p className="panel-caption">Evidence: {new Date(value.evidence_timestamp).toLocaleTimeString()} · {value.source_id}</p>}</main>);
}
