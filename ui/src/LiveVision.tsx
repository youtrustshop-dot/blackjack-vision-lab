import {useEffect,useRef,useState} from 'react';
import {createRoot,Root} from 'react-dom/client';
import {createPortal} from 'react-dom';
import {Download,ExternalLink,Monitor,Play,ScanEye,Square} from 'lucide-react';
import {api,download,fetchApi,Rules,Snapshot} from './api';
import {ScreenShare,captureScreenFrame,screenSharingError} from './screen-sharing';
import {LiveVideoLoop} from './live-loop';
import {LiveAnalysis} from './live-analysis';
import {nativeControl,publishView} from './native-advisor';
import ClefVerification,{useClefVerification} from './ClefVerification';
import {verificationImage,VisualEvidence} from './clef-evidence';
import {FrameMonitor} from './frame-monitor';
import {SessionRecording,saveVideo} from './session-recording';
import {DemoVideoSource} from './demo-source';
import {getLanguage,t} from './i18n';
import {localize} from './localize';
import {handValue} from './preferences';
import {captureGeometry,cropLayout,previewPoint,sourceDetectionBox,Layout} from './capture-geometry';
import './live.css';

const actions:Record<string,string>={hit:'Hit',stand:'Stand',double:'Double',split:'Split',surrender:'Surrender',continue:'Continue',insurance:'Insurance',decline_insurance:'Decline insurance'};
const percent=(value:unknown)=>typeof value==='number'?(value*100).toFixed(1)+'%':'—';
const number=(value:unknown,d=2)=>typeof value==='number'?value.toFixed(d):'—';
const analysisLabels:Record<string,string>={ready:'In progress',pending:'In progress',busy:'Waiting for an analysis slot',complete:'Complete',timeout:'Budget reached',error:'Not available',not_available:'Not available',unavailable:'Not available'};

export function LiveAdvisor({report,stale,compact=false}:{report:any;stale:boolean;compact?:boolean}){
 const decision=!stale?report?.decision:null,advice=!stale?report?.advice:null;
 const best=advice?.best_action||decision?.best_action,row=decision?.actions?.[best];
 const hand=advice?.hand||(!stale&&report?.gate?.solver_allowed&&report?.player?.length?handValue(report.player):null);
 const state=report?.phase==='settled'?'Hand complete':stale&&report?'Refresh the video':report?.gate?.reasons?.length?'Check the table':'Connect a source';
 return localize(<section className={'live-advisor '+(compact?'compact':'')} aria-label="Probability estimates">
  <div className="advisor-heading"><span className={'status-dot '+(best?'ok':'')}/><span>{best?'NEXT ACTION':'TABLE STATUS'}</span><small>{advice?.basis==='observed-composition'?'Composition estimate':best?'Basic strategy':'Video evidence'}</small></div>
  <h2 className={'action-title action-'+(best||'waiting')}>{best?actions[best]||best:state}</h2>
  {hand&&<div className="hand-value"><strong>{hand.total}</strong><span>{hand.soft?'Soft total':'Hard total'}{hand.soft&&' · '+hand.hard_total+' or '+hand.total}</span>{hand.ace_values?.map((value:number,i:number)=><span className="ace-chip" key={i}>A = {value}<small>1 / 11</small></span>)}</div>}
  <p className="advisor-cards"><span>Player <b>{report?.player?.join(' · ')||'—'}</b></span><span>Dealer <b>{report?.dealer?.join(' · ')||'—'}</b></span></p>
  {!compact&&<div className="probability-grid"><div><span>Positive outcome</span><strong>{percent(row?.win)}</strong></div><div><span>Push</span><strong>{percent(row?.push)}</strong></div><div><span>Negative outcome</span><strong>{percent(row?.loss)}</strong></div></div>}
  {compact&&row&&<p className="compact-probability">Positive outcome <b>{percent(row.win)}</b> · EV {number(row.ev,3)}</p>}
  <div className="advisor-count"><span>True count <b className={(report?.true_count||0)>=2?'positive':(report?.true_count||0)<=-2?'negative':''}>{number(report?.true_count)}</b></span><span>Running count <b>{report?.running_count??'—'}</b></span><span>Observed <b>{report?.observed_cards??0}</b></span></div>
  {report?.count_reliable===false&&<p className="gate-note">Count unverified · {report?.count_reasons?.[0]||'Waiting for consistent observed history.'}</p>}
  {report?.count_scope&&<p className="count-scope">{report.count_scope==='from declared fresh shoe'?'From declared fresh shoe':'Observed cards only'}</p>}
  {!best&&<p className="gate-note" role="status">{stale&&report?'Refresh the source before acting.':report?.phase==='settled'?'Wait for the next deal.':report?.gate?.reasons?.[0]||'Share a table, run the demo, or confirm cards manually.'}</p>}
  <details className="advisor-details"><summary>Why this action & advanced details</summary><div className="advisor-detail-body">
   {advice&&<div className="strategy-comparison"><div><span>Basic policy</span><b>{actions[advice.basic_action]||advice.basic_action}</b></div><div><span>Hi-Lo reference</span><b>{advice.count_comparison_reliable?(actions[advice.count_action]||advice.count_action):'Unavailable · incomplete history'}</b></div><div><span>Composition estimate</span><b>{decision?actions[decision.best_action]||decision.best_action:'Not available'}</b></div></div>}
   {advice?.explanation&&<ol>{advice.explanation.map((line:string,i:number)=><li key={i}>{line}</li>)}</ol>}
   {row&&<><div className="advisor-ev"><span>Estimated EV per initial wager</span><b>{number(row.ev,4)}</b></div><p>95% sampling interval: {percent(row.win_ci95?.[0])} – {percent(row.win_ci95?.[1])}<br/>{decision.samples_per_action} outcomes per action · Monte Carlo</p><p>{decision.ranking_resolved?'EV ranking separated':'EV intervals overlap; basic strategy remains the primary recommendation.'}</p></>}
   {decision?.insurance_blackjack_probability!==undefined&&<p>Dealer blackjack: {percent(decision.insurance_blackjack_probability)} · Insurance EV: {number(decision.insurance_ev,4)}</p>}
   {decision?.actions&&Object.keys(decision.actions).length>0&&<div className="live-action-table"><div><b>Action</b><b>EV</b><b>Positive</b><b>Push</b><b>Negative</b></div>{Object.entries(decision.actions).map(([name,value]:[string,any])=><div key={name} className={name===best?'best':''}><span>{actions[name]||name}</span><span>{number(value.ev,4)}</span><span>{percent(value.win)}</span><span>{percent(value.push)}</span><span>{percent(value.loss)}</span></div>)}</div>}
   <p>{report?.count_history==='complete'?'Full observed history from a declared fresh shoe.':report?.count_history==='compromised'?'Observation history is incomplete. Declare a new shoe to restore the count.':'Count covers observed cards only. Earlier cards are unknown.'}</p><p>Remaining inventory: {report?.physical_remaining??'—'} cards. A positive true count describes a higher proportion of tens and aces in the estimated pool; it does not guarantee an outcome.</p>
   {report?.analysis&&<p><span>EV analysis</span>: <span>{analysisLabels[report.analysis.status]||'Not available'}</span>. <span>Basic strategy remains available while estimates run.</span></p>}
   <p>Basic strategy is available offline. Sampling intervals describe simulation uncertainty, not recognition accuracy. EV describes the current action, not the next-round betting edge.</p>
  </div></details>
  <p className="analysis-disclaimer">Analysis and education only. Not financial advice. No guaranteed outcomes.</p>
 </section>);
}

function tableHeight(corners:number[][],width:number,height:number){if(corners.length!==4)return Math.max(600,Math.min(1600,Math.round(960*height/Math.max(1,width))));const edge=(a:number,b:number)=>Math.hypot((corners[a][0]-corners[b][0])*width,(corners[a][1]-corners[b][1])*height);return Math.max(600,Math.min(1600,Math.round(960*(edge(0,3)+edge(1,2))/Math.max(1,edge(0,1)+edge(3,2)))))}
export default function LiveVision({rules,connected,acquireSource,releaseSource,interval=350,monitorOnly=false,tableName='Table 1',demoSeed=42,defaultSamples=1500}:{rules:Rules;connected:boolean;acquireSource?:()=>Promise<MediaStream>;releaseSource?:(stream:MediaStream)=>void;interval?:number;monitorOnly?:boolean;tableName?:string;demoSeed?:number;defaultSamples?:number}){
 const video=useRef<HTMLVideoElement>(null),owner=useRef(new ScreenShare()),demo=useRef<DemoVideoSource|null>(null),loop=useRef<LiveVideoLoop|null>(null);
 const [profile,setProfile]=useState('automatic'),[layout,setLayout]=useState<Layout>({}),[regionName,setRegionName]=useState('table');
 const regionStart=useRef<[number,number]|null>(null),diagnosticNext=useRef(false);
 const [diagnosticStatus,setDiagnosticStatus]=useState('');
 const [regionPixels,setRegionPixels]=useState<{name:string;url:string;size:string}[]>([]);
 const advisorId=useRef(crypto.randomUUID()),viewEpoch=useRef(0),nativeStream=useRef<string|null>(null);
 const progressive=useRef(new LiveAnalysis());
 const identity=useRef<string|null>(null),generation=useRef(0),sourceGeneration=useRef(0),mounted=useRef(true),abort=useRef<AbortController|null>(null);
 const [stream,setStream]=useState<MediaStream|null>(null),[source,setSource]=useState(''),[pending,setPending]=useState(false),[observing,setObserving]=useState(false),[error,setError]=useState('');
 const [rawReport,setReport]=useState<any>(null),[lastSeen,setLastSeen]=useState(0),[stale,setStale]=useState(true),[corners,setCorners]=useState<number[][]>([]),[selecting,setSelecting]=useState(false);
 const [samples,setSamples]=useState(defaultSamples),[fresh,setFresh]=useState(false),[manualTurn,setManualTurn]=useState(false),[bot,setBot]=useState(true),[demoState,setDemoState]=useState<Snapshot|null>(null);
 const [metrics,setMetrics]=useState({sent:0,skipped:0,latency:0,received:0}),[advisorOpen,setAdvisorOpen]=useState(false),[inlineAdvisor,setInlineAdvisor]=useState(false),[advisorOpening,setAdvisorOpening]=useState(false),floating=useRef<{window:Window;root:Root}|null>(null),advisorGeneration=useRef(0);
 const [verify,setVerify]=useState(false),[evidence,setEvidence]=useState<VisualEvidence|null>(null);
 const verificationEnabled=useRef(verify);verificationEnabled.current=verify;
 const verification=useClefVerification(evidence,verify);
 const disagreement=verification.result?.comparison?.status==='disagreement';
 const report=disagreement&&rawReport?{...rawReport,advice:null,decision:null,gate:{solver_allowed:false,reasons:verification.result.comparison.issues}}:rawReport;
 const recording=useRef(new SessionRecording()),[recordingOn,setRecordingOn]=useState(false);
 const language=getLanguage();

 const stopObserver=()=>{
  generation.current++;progressive.current.stop();loop.current?.stop();loop.current=null;abort.current?.abort();abort.current=null;
  const old=identity.current;identity.current=null;if(old)void fetchApi('/live/'+old,{method:'DELETE'}).catch(()=>{});
  if(mounted.current){setObserving(false);setReport(null);setEvidence(null);setStale(true);setLastSeen(0)}
 };
 const sourceObserved=useRef(false);
 const shared=useRef<MediaStream|null>(null);
 const stop=()=>{recording.current.stop();sourceGeneration.current++;sourceObserved.current=false;stopObserver();owner.current.stop();if(shared.current){releaseSource?.(shared.current);shared.current=null}demo.current?.dispose();demo.current=null;if(mounted.current){setStream(null);setPending(false);setSource('');setDemoState(null)}};
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;advisorGeneration.current++;stop();const previous=floating.current;floating.current=null;previous?.root.unmount();previous?.window.close()}},[]);
 useEffect(()=>{if(!connected)stopObserver()},[connected]);
 useEffect(()=>{const timer=setInterval(()=>setStale(!lastSeen||performance.now()-lastSeen>2200),200);return()=>clearInterval(timer)},[lastSeen]);
 useEffect(()=>{const target=floating.current;if(target&&!target.window.closed){target.window.document.documentElement.lang=language;target.root.render(localize(<LiveAdvisor report={report} stale={stale} compact/>))}},[report,stale,language]);

 useEffect(()=>{
  if(!stream||profile!=='native'){setRegionPixels([]);return}
  const refresh=()=>{const target=video.current;if(!target||!target.videoWidth)return;
   setRegionPixels(Object.entries(layout).filter(([name])=>name!=='table').map(([name,rect])=>{
    const {source_rect:[x,y,w,h]}=captureGeometry(target.videoWidth,target.videoHeight,rect,null);
    const preview=document.createElement('canvas');preview.width=Math.min(240,w);preview.height=Math.max(1,Math.round(h*preview.width/w));
    preview.getContext('2d')!.drawImage(target,x,y,w,h,0,0,preview.width,preview.height);
    return {name,url:preview.toDataURL('image/png'),size:w+' × '+h+' source pixels'};
   }));
  };refresh();const timer=setInterval(refresh,1000);return()=>clearInterval(timer);
 },[stream,profile,layout]);
 const startObserver=async()=>{
  stopObserver();if(!video.current||!stream||!connected||monitorOnly)return;
  if(corners.length!==0&&corners.length!==4){setError('Select all four table corners before observing.');return}
  const attempt=generation.current;setError('');setPending(true);
  try{
   if(profile==='native'&&!['table','dealer','player:0'].every(name=>layout[name]))throw new Error('Select the table, dealer and player card regions first.');
   viewEpoch.current=0;
   const nativeLayout=profile==='native'?cropLayout(layout,video.current.videoWidth,video.current.videoHeight):undefined;
   const configuration=await api('/live',{rules,samples,layout:nativeLayout,output_height:tableHeight(corners,video.current.videoWidth,video.current.videoHeight),corners:profile==='native'?null:corners.length===4?corners:null,fresh_shoe:(source==='demo'&&!sourceObserved.current)||fresh,manual_turn:manualTurn});
   if(!mounted.current||attempt!==generation.current){void fetchApi('/live/'+configuration.stream_id,{method:'DELETE'});return}
   identity.current=configuration.stream_id;sourceObserved.current=true;setObserving(true);
   const target=video.current!;const id=configuration.stream_id;
   const monitor=new FrameMonitor(),canvas=document.createElement('canvas');canvas.width=96;canvas.height=54;
   const monitorContext=canvas.getContext('2d',{willReadFrequently:true});let motionEpoch=0,region:number[]|null=null,imageSize:number[]|null=null;
   loop.current=new LiveVideoLoop(target,async(sequence)=>{
    const capturedAt=Date.now(),began=performance.now(),capturedEpoch=motionEpoch,controller=new AbortController();abort.current=controller;
    const timeout=setTimeout(()=>controller.abort(),6000);
    try{
     const capture=captureGeometry(target.videoWidth,target.videoHeight,profile==='native'?layout.table:undefined,profile==='native'?null:1920);
     const image=await captureScreenFrame(target,{region:profile==='native'?layout.table:undefined,maxEdge:profile==='native'?null:1920});
     const saveDiagnostic=diagnosticNext.current;diagnosticNext.current=false;
     if(attempt!==generation.current)return;
     const response=await fetchApi('/live/'+id+'/frame?sequence='+sequence+'&timestamp='+(began/1000)+(saveDiagnostic?'&diagnostic=true':''),{method:'POST',body:image,signal:controller.signal,headers:{'Content-Type':'image/png','X-BJLAB-Capture':JSON.stringify({...capture,captured_monotonic_ms:began,captured_epoch_ms:capturedAt,motion_epoch:capturedEpoch,table_name:tableName})}});
     if(saveDiagnostic&&response.ok){const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='private-vision-diagnostic.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);setDiagnosticStatus('Saved locally: exact backend input, transforms, crops and observation.');return}
     const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'Video processing failed.');
     if(!mounted.current||attempt!==generation.current)return;
     region=value.table_bounds;imageSize=value.image_size;
     if(capturedEpoch===motionEpoch){setReport(value);setLastSeen(began);setStale(performance.now()-began>2200);setError('');if(verificationEnabled.current&&value.gate?.solver_allowed){const visualImage=await verificationImage(image,corners.length?null:value);if(capturedEpoch===motionEpoch&&attempt===generation.current)setEvidence({key:[attempt,capturedEpoch,value.round,value.player.join(','),value.dealer.join(',')].join(':'),image:visualImage,report:value,corners:corners.length?corners:undefined,output_height:tableHeight(corners,target.videoWidth,target.videoHeight)})}else setEvidence(null)}
     if(capturedEpoch===motionEpoch&&value.state_id&&['ready','pending','busy'].includes(value.analysis?.status)){
      progressive.current.watch([attempt,capturedEpoch,id,value.state_id].join(':'),async signal=>{
       const response=await fetchApi('/live/'+id+'/analysis?state_id='+encodeURIComponent(value.state_id),{signal});
       if(!response.ok)throw new Error('Analysis is no longer current.');return response.json();
      },patch=>{if(mounted.current&&attempt===generation.current&&capturedEpoch===motionEpoch&&patch.state_id===value.state_id)setReport((current:any)=>current?.state_id===patch.state_id?{...current,...patch}:current)});
     }else if(capturedEpoch===motionEpoch)progressive.current.stop();
     setMetrics({sent:sequence+1,skipped:loop.current?.skipped||0,latency:performance.now()-began,received:loop.current?.received||0});
    }finally{clearTimeout(timeout)}
   },e=>{setReport(null);setStale(true);setError(e instanceof Error&&e.name==='AbortError'?'Video processing timed out. Waiting for a fresh observation.':String(e instanceof Error?e.message:e))},interval,undefined,()=>{
    if(!monitorContext||attempt!==generation.current)return;
    if(profile==='native'&&layout.table){const [x,y,w,h]=captureGeometry(target.videoWidth,target.videoHeight,layout.table,null).source_rect;monitorContext.drawImage(target,x,y,w,h,0,0,96,54)}
    else if(region&&imageSize&&!corners.length){const sx=target.videoWidth/imageSize[0],sy=target.videoHeight/imageSize[1];monitorContext.drawImage(target,region[0]*sx,region[1]*sy,region[2]*sx,region[3]*sy,0,0,96,54)}
    else monitorContext.drawImage(target,0,0,96,54);
    if(monitor.observe(monitorContext.getImageData(0,0,96,54).data).motion>.008){motionEpoch++;viewEpoch.current=motionEpoch;void publishView(id,{epoch:motionEpoch,stale:true,verification:verificationEnabled.current?'pending':'disabled'}).catch(()=>{});progressive.current.stop();setReport(null);setEvidence(null);setStale(true)}
   });
   loop.current.start();
  }catch(e){if(mounted.current&&attempt===generation.current)setError(e instanceof Error?e.message:String(e))}
  finally{if(mounted.current&&attempt===generation.current)setPending(false)}
 };
 useEffect(()=>{
  if(!stream||!video.current)return;
  const target=video.current;target.srcObject=stream;
  const ended=()=>stop();stream.getVideoTracks().forEach(track=>track.addEventListener('ended',ended));
  void target.play().catch(()=>setError('Video preview could not start. Stop and retry.'));
  return()=>{stream.getVideoTracks().forEach(track=>track.removeEventListener('ended',ended));target.srcObject=null};
 },[stream]);
 const start=async(kind:'screen'|'demo')=>{
  stop();setError('');setCorners([]);setLayout({});setSelecting(false);setPending(true);const attempt=sourceGeneration.current;
  try{
   let next:MediaStream|null;
   if(kind==='screen'){next=acquireSource?await acquireSource():await owner.current.start();if(acquireSource&&next)shared.current=next}
   else{const source=new DemoVideoSource(rules,value=>{if(mounted.current&&attempt===sourceGeneration.current)setDemoState(value)},demoSeed);demo.current=source;next=await source.start();setBot(true)}
   if(!mounted.current||attempt!==sourceGeneration.current){if(kind==='screen'&&acquireSource&&next){releaseSource?.(next);if(shared.current===next)shared.current=null}else next?.getTracks().forEach(track=>track.stop());return}
   if(next){setSource(kind);setStream(next);if(kind==='screen'&&!monitorOnly){window.dispatchEvent(new CustomEvent('bjlab:advisor-focus',{detail:advisorId.current}));setInlineAdvisor(true);setAdvisorOpen(true)}}
  }catch(e){if(mounted.current&&attempt===sourceGeneration.current)setError(screenSharingError(e))}
  finally{if(mounted.current&&attempt===sourceGeneration.current)setPending(false)}
 };
 const closeAdvisor=()=>{if(nativeStream.current){void nativeControl('hide',nativeStream.current).catch(()=>{});nativeStream.current=null}advisorGeneration.current++;const previous=floating.current;floating.current=null;previous?.root.unmount();previous?.window.close();setAdvisorOpen(false);setInlineAdvisor(false);setAdvisorOpening(false)};
 useEffect(()=>{
  const id=identity.current;if(!id)return;
  const status=verify?(verification.result?.comparison?.status||'pending'):'disabled';
  void publishView(id,{epoch:viewEpoch.current,stale,state_id:report?.state_id,verification:['disabled','pending','agreement','disagreement'].includes(status)?status:'inconclusive'}).catch(()=>{});
 },[report,stale,verify,verification.result]);
 useEffect(()=>{
  if(!advisorOpen)return;const timer=setInterval(()=>{if(nativeStream.current)void api('/native/advisor/status').then(value=>{if(value.stream_id===nativeStream.current&&!value.visible&&!value.pending){nativeStream.current=null;setAdvisorOpen(false);setInlineAdvisor(false)}}).catch(()=>{})},500);return()=>clearInterval(timer);
 },[advisorOpen]);
 const openAdvisor=async()=>{
  closeAdvisor();const attempt=advisorGeneration.current;window.dispatchEvent(new CustomEvent('bjlab:advisor-focus',{detail:advisorId.current}));setInlineAdvisor(true);setAdvisorOpen(true);setAdvisorOpening(true);
  try{
   const host=await api('/native/advisor/status').catch(()=>({available:false}));
   if(host.available){
    if(!identity.current)throw new Error('Start observing the table before opening the native advisor.');
    await nativeControl('open',identity.current,tableName);
    for(let n=0;n<20;n++){await new Promise(resolve=>setTimeout(resolve,150));const status=await api('/native/advisor/status');
     if(!mounted.current||attempt!==advisorGeneration.current){void nativeControl('hide',identity.current||undefined);return}
     if(!status.pending){if(status.error||!status.visible)throw new Error(status.error||'The native window is unavailable.');nativeStream.current=identity.current;setInlineAdvisor(false);setAdvisorOpen(true);return}
    }throw new Error('Native advisor did not acknowledge opening.');
   }
   const pip=(window as Window&{documentPictureInPicture?:{requestWindow:(options:{width:number;height:number})=>Promise<Window>}}).documentPictureInPicture;
   let win:Window|null=null;
   if(pip){let expired=false;let timer:ReturnType<typeof setTimeout>|undefined;const requested=pip.requestWindow({width:360,height:300});
    void requested.then(value=>{if(expired||attempt!==advisorGeneration.current||!mounted.current)value.close()}).catch(()=>{});
    try{win=await Promise.race([requested,new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(new Error('Picture-in-Picture unavailable')),1800)})])}catch{expired=true}finally{clearTimeout(timer)}
   }
   if(!mounted.current||attempt!==advisorGeneration.current){win?.close();return}
   if(!win){window.dispatchEvent(new CustomEvent('bjlab:advisor-focus',{detail:advisorId.current}));setInlineAdvisor(true);setAdvisorOpen(true);setError('Advisor is shown in this page. Use Chrome or Edge for a separate always-on-top window.');return}
   win.document.title='Blackjack Vision Lab · Live advisor';win.document.documentElement.lang=language;
   win.document.querySelectorAll('style,link[rel="stylesheet"]').forEach(node=>node.remove());
   document.querySelectorAll('style,link[rel="stylesheet"]').forEach(node=>{const clone=node.cloneNode(true) as HTMLElement;if(node instanceof HTMLLinkElement)clone.setAttribute('href',node.href);win.document.head.appendChild(clone)});
   win.document.body.className='advisor-window';const mount=win.document.createElement('div');win.document.body.replaceChildren(mount);
   win.document.title=tableName+' · Blackjack Vision Lab';const root=createRoot(mount);floating.current={window:win,root};setInlineAdvisor(false);setAdvisorOpen(true);root.render(localize(<LiveAdvisor report={report} stale={stale} compact/>));
   win.addEventListener('pagehide',()=>{if(floating.current?.window===win){floating.current=null;root.unmount();if(mounted.current){window.dispatchEvent(new CustomEvent('bjlab:advisor-focus',{detail:advisorId.current}));setInlineAdvisor(false);setAdvisorOpen(false)}}},{once:true});
  }catch(e){if(mounted.current&&attempt===advisorGeneration.current){window.dispatchEvent(new CustomEvent('bjlab:advisor-focus',{detail:advisorId.current}));setInlineAdvisor(true);setAdvisorOpen(true);setError(e instanceof Error?e.message:String(e))}}
  finally{if(mounted.current&&attempt===advisorGeneration.current)setAdvisorOpening(false)}
 };
 useEffect(()=>{const focus=(event:Event)=>{if((event as CustomEvent).detail!==advisorId.current)closeAdvisor()};window.addEventListener('bjlab:advisor-focus',focus);return()=>window.removeEventListener('bjlab:advisor-focus',focus)},[]);
 const openBrowser=async()=>{try{await api('/live/browser',{});setError('Opened the local app in your browser. Keep the desktop app open while sharing.')}catch(e){setError(e instanceof Error?e.message:String(e))}};
 return localize(<div className="live-workspace">
  <section className="panel live-controls"><div><div className="section-label">CONTINUOUS SCREEN VIDEO</div><h2>Share once. Follow the whole game.</h2><p>Choose a screen, window or browser tab. Observation continues automatically; no image capture button is needed.</p></div><div className="live-buttons">
   <button className="button primary" disabled={pending||!connected} onClick={()=>void start('screen')}><Monitor size={16}/>Share screen</button>
   <button hidden={monitorOnly} className="button secondary" disabled={pending||!connected} onClick={()=>void start('demo')}><Play size={16}/>Run lab demo</button>
   {stream&&<button className="button secondary" onClick={stop}><Square size={14}/>Stop video</button>}
   {pending&&<button className="button secondary" onClick={stop}>Cancel</button>}
   <button hidden={monitorOnly} className="button secondary" onClick={()=>{if(advisorOpen)closeAdvisor();else{window.dispatchEvent(new CustomEvent('bjlab:advisor-focus',{detail:advisorId.current}));setInlineAdvisor(true);setAdvisorOpen(true)}}}><ExternalLink size={14}/>{advisorOpen?'Close advisor':'Floating advisor'}</button>
   {advisorOpen&&<button className="button secondary" disabled={advisorOpening} onClick={()=>void openAdvisor()}>{advisorOpening?'Opening advisor…':'Pop out advisor'}</button>}
   <a className="button secondary" href="/?simulator=1" target="_blank" rel="noopener">Open simulator window</a>
  </div></section>
  {error&&<p className="tool-error live-error" role="alert">{error}</p>}
  <div className="live-columns"><section className="panel live-video-panel"><div className="panel-header"><h2><ScanEye size={17}/>{source==='demo'?'Lab video demo':'Screen video'}</h2><span className="badge" role="status">{observing||(monitorOnly&&stream)?'Video connected':stream?'Video paused':'Waiting for video'}</span></div>
   {stream?<div className={'live-video-wrap '+(selecting?'selecting':'')}
    onPointerDown={e=>{if(profile!=='native'||!selecting||!video.current)return;regionStart.current=previewPoint(e.clientX,e.clientY,video.current.getBoundingClientRect(),video.current.videoWidth,video.current.videoHeight);e.currentTarget.setPointerCapture(e.pointerId)}}
    onPointerUp={e=>{if(profile!=='native'||!selecting||!regionStart.current||!video.current)return;const end=previewPoint(e.clientX,e.clientY,video.current.getBoundingClientRect(),video.current.videoWidth,video.current.videoHeight);const start=regionStart.current;regionStart.current=null;if(!end)return;const rect:[number,number,number,number]=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.abs(end[0]-start[0]),Math.abs(end[1]-start[1])];if(rect[2]<.005||rect[3]<.005)return;setLayout(v=>({...v,[regionName]:rect}));setSelecting(false)}}
    onClick={e=>{if(profile==='native'||!selecting||corners.length>=4||!video.current)return;const point=previewPoint(e.clientX,e.clientY,video.current.getBoundingClientRect(),video.current.videoWidth,video.current.videoHeight);if(point)setCorners(previous=>[...previous,point])}}>
    <video ref={video} muted autoPlay playsInline aria-label="Continuous shared video" onLoadedData={()=>void startObserver()}/>
    <svg className="live-detections" viewBox={'0 0 '+(video.current?.videoWidth||960)+' '+(video.current?.videoHeight||600)} aria-label="Live recognized cards">{corners.length===0&&(report?.detections||[]).map((d:any,i:number)=>{const [x,y,w,h]=sourceDetectionBox(d.bbox,report?.capture_geometry);return <g key={i}><rect x={x} y={y} width={w} height={h}/><text x={x+3} y={Math.max(18,y-7)}>{d.face_down?'BACK':[d.rank,d.suit].filter(Boolean).join(' ')}</text></g>})}</svg>
    {corners.map((c,i)=><span className="live-corner" key={i} style={{left:c[0]*100+'%',top:c[1]*100+'%'}}>{i+1}</span>)}
    {profile==='native'&&Object.entries(layout).map(([name,[x,y,w,h]])=><div className="selected-native-region" key={name} style={{left:x*100+'%',top:y*100+'%',width:w*100+'%',height:h*100+'%'}}>{name}</div>)}
   </div>:<div className="live-placeholder"><Monitor size={38}/><h3>Give the lab a live video source.</h3><p>Share your simulation, or run the lab demo to test video → recognition → tracking → advice.</p></div>}
   <div className="live-config" hidden={monitorOnly}><label>Samples per action<select disabled={observing||pending} value={samples} onChange={e=>setSamples(Number(e.target.value))}><option value="500">500 · fast</option><option value="1500">1,500 · balanced</option><option value="5000">5,000 · precise</option></select></label><label><input type="checkbox" disabled={observing||pending} checked={fresh} onChange={e=>setFresh(e.target.checked)}/>Observe from a new shoe</label><label><input type="checkbox" disabled={observing||pending} checked={manualTurn} onChange={e=>setManualTurn(e.target.checked)}/>Player turn (manual layout)</label>
    {stream&&<button className="button secondary" onClick={()=>{if(observing)stopObserver();else void startObserver()}} disabled={pending}>{observing?'Stop observing':'Start observing'}</button>}
   </div>
   {stream&&!monitorOnly&&<div className="live-calibration"><label>Recognition profile <select value={profile} onChange={e=>{stopObserver();setProfile(e.target.value);setSelecting(false);setCorners([])}}><option value="automatic">Automatic · current baseline</option><option value="native">Calibrated corners · research</option></select></label>
    {profile==='native'&&<><label>Region <select value={regionName} onChange={e=>setRegionName(e.target.value)}><option value="table">Table</option><option value="dealer">Dealer cards</option><option value="player:0">Player cards</option><option value="controls">Controls (diagnostic)</option></select></label><button className="button secondary" onClick={()=>{stopObserver();setSelecting(true)}}>Drag a region on the video</button><button className="button secondary" onClick={()=>void startObserver()} disabled={observing||!layout.table||!layout.dealer||!layout['player:0']}>Apply native regions</button><p>Only the selected table is uploaded. Card regions exclude advertising, previews and the advisor. Keep the window fixed; after scrolling or resizing, recalibrate. Confirm Player turn for research advice; complete card counts are not certified for this profile.</p><div className="native-region-pixels">{regionPixels.map(region=><figure key={region.name}><figcaption>{region.name} · {region.size}</figcaption><img src={region.url} alt={region.name+" pixels selected for analysis"}/></figure>)}</div><details><summary>Normalized regions</summary><pre>{JSON.stringify(layout,null,2)}</pre></details></>}
    <button className="button secondary" disabled={!observing} onClick={()=>{diagnosticNext.current=true;setDiagnosticStatus('The next processed observation will be saved locally.')}}>Save private vision diagnostic</button><span role="status">{diagnosticStatus}</span>
   </div>}
   {stream&&!monitorOnly&&profile==="automatic"&&<div className="live-calibration"><button className="text-button" onClick={()=>{stopObserver();setSelecting(v=>!v);setCorners([])}}>Table calibration</button><span>Selected corners: {corners.length} / 4</span><button className="text-button" onClick={()=>{stopObserver();setCorners([]);setSelecting(false)}}>Clear corners</button><button className="button secondary" disabled={corners.length!==4||pending} onClick={()=>{setSelecting(false);void startObserver()}}>Apply calibration</button><p>For a full screen, select the table corners: top left, top right, bottom right, bottom left. Keep its position fixed while observing.</p></div>}
   {source==='demo'&&demoState&&<div className="live-demo-actions"><button className="button secondary" onClick={()=>{demo.current?.setBot(!bot);setBot(v=>!v)}}>{bot?'Pause bot':'Resume bot'}</button>{demoState.available_actions.map(action=><button key={action} className="button secondary" onClick={()=>void demo.current?.action(action).catch(e=>setError(e.message))}>{action==='deal'?'Deal':action==='shuffle'?'New shoe':actions[action]||action}</button>)}<span>Round {demoState.round_id} · {demoState.phase}</span></div>}
   <label className="toggle-label" hidden={monitorOnly}><input type="checkbox" checked={verify} onChange={e=>setVerify(e.target.checked)}/>Independent Clef verification (experimental)</label>
   {verify&&<ClefVerification result={verification.result} busy={verification.busy}/>}
   {stream&&<details className="live-details"><summary>Local video replay</summary><p>Optionally save the selected video and observed events on this computer. Recording is off by default. No video is sent to an external service.</p><button className="button secondary" onClick={()=>{if(recordingOn){recording.current.stop();return}try{recording.current.start(stream,(blob,metadata)=>{saveVideo(blob,'blackjack-session.webm');download('blackjack-video-timing.json',metadata);if(mounted.current)setRecordingOn(false)},message=>{if(mounted.current)setError(message)});setRecordingOn(true)}catch(e){setError(e instanceof Error?e.message:String(e))}}}>{recordingOn?'Stop & save video':'Record video locally'}</button></details>}
   <div className="live-metrics"><span>Video processing <b>{number(metrics.latency,0)} ms</b></span><span>Frames monitored <b>{metrics.received}</b></span><span>Card analyses <b>{metrics.sent}</b></span><span>Skipped while busy <b>{metrics.skipped}</b></span></div>
   <p className="panel-caption" hidden={monitorOnly}>Processing runs locally. The preview is video; the analysis samples it automatically with one upload in flight. Guidance expires when the video stops updating.</p>
   <details className="live-details" hidden={monitorOnly}><summary>Recognition scope and probability method</summary><p>Recognition supports lab cards and compatible classic green casino tables. Include printed corners, hand totals and enabled English or Italian action buttons. The largest compatible table is located automatically. Counts cover observed cards; declare external shuffles explicitly. Unreadable or multiple active hands need confirmation.</p><p>Win, push and loss describe net profit of the active hand, including any new splits. Existing other hands are excluded. EV estimates use finite-pool Monte Carlo with generated basic continuation; sampling intervals do not measure perception error.</p></details>
   <p className="panel-caption">Display sharing needs Chrome or Edge on localhost. <button className="text-button" onClick={()=>void openBrowser()}>Open in default browser</button></p>
  </section>{monitorOnly?<section className="live-advisor"><h2>Visual monitor</h2><p>This source is registered separately. Poker strategy and poker card recognition are not supported; no blackjack recommendation is applied to this game.</p></section>:<LiveAdvisor report={report} stale={stale}/>}</div>
  {report&&<div className="live-export"><button className="button secondary" onClick={()=>download('live-observation.json',report)}><Download size={14}/>Export observation</button><button className="button secondary" onClick={()=>identity.current&&void api('/live/'+identity.current+'/events').then(value=>download('live-events.json',value))}><Download size={14}/>Export observed events</button></div>}
  {inlineAdvisor&&createPortal(localize(<aside className="inline-live-advisor" aria-label="Floating live advisor"><div className="floating-table-name">{tableName}</div><button className="text-button" onClick={closeAdvisor}>Close advisor</button><LiveAdvisor report={report} stale={stale} compact/></aside>),document.body)}
 </div>);
}
