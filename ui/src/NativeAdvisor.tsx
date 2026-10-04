import {useEffect,useState} from 'react';
import {api} from './api';
import CompactAdvisor from './CompactAdvisor';
import {nativeControl} from './native-advisor';
import {evidenceExpiry} from './advisor-evidence';
import {advisorSnapshotCurrent} from './compact-advisor';

export default function NativeAdvisor(){
 const stream=new URLSearchParams(location.search).get('advisor')!;
 const [status,setStatus]=useState<any>(null),[value,setValue]=useState<any>(null),[expires,setExpires]=useState(0),[now,setNow]=useState(performance.now()),[error,setError]=useState('');
 useEffect(()=>{let active=true,timer:ReturnType<typeof setTimeout>;
  const poll=async()=>{const began=performance.now();try{
   const [state,host]=await Promise.all([api('/native/advisor/'+stream+'/state'),api('/native/advisor/status')]);
   if(active){setValue(state);setStatus(host);setExpires(advisorSnapshotCurrent(state,host,stream)?evidenceExpiry(state.evidence_ttl_ms,began,performance.now()):0);setError('')}
  }catch(e){if(active){setValue(null);setExpires(0);setError(e instanceof Error?e.message:String(e))}}
  finally{if(active)timer=setTimeout(poll,350)}};void poll();const tick=setInterval(()=>setNow(performance.now()),150);
  return()=>{active=false;clearTimeout(timer);clearInterval(tick)};
 },[stream]);
 const action=async(operation:'hide'|'topmost'|'minimize'|'reset',topmost?:boolean)=>{try{await nativeControl(operation,stream,undefined,topmost)}catch(e){setError(e instanceof Error?e.message:String(e))}};
 const stale=!advisorSnapshotCurrent(value,status,stream)||now>=expires;
 return <main className="external-advisor">
  <header className="external-advisor-toolbar"><span title="Drag the native title bar to move this window">{status?.table_name||'Live advisor'}</span><button title="Always on top" aria-label="Always on top" aria-pressed={status?.topmost||false} onClick={()=>void action('topmost',!status?.topmost)}>Pin</button><button title="Reset advisor position and size" aria-label="Reset advisor position" onClick={()=>void action('reset')}>↺</button><button title="Minimize advisor" aria-label="Minimize advisor" onClick={()=>void action('minimize')}>−</button><button title="Close advisor" aria-label="Close advisor" onClick={()=>void action('hide')}>×</button></header>
  {status?.tables?.length>1&&<select aria-label="Selected table" value={stream} onChange={e=>{setValue(null);setExpires(0);const table=status.tables.find((t:any)=>t.stream_id===e.target.value);void nativeControl('open',table.stream_id,table.table_name).catch(e=>setError(e instanceof Error?e.message:String(e)))}}>{status.tables.map((table:any)=><option key={table.stream_id} value={table.stream_id}>{table.table_name}</option>)}</select>}
  {error&&<div className="mini-error" role="alert" title={error}>{error}</div>}
  <CompactAdvisor report={value?.report} stale={stale} ageMs={value?.evidence_timestamp?Date.now()-value.evidence_timestamp:undefined}/>
 </main>;
}
