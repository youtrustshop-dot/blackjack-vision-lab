import {useEffect,useRef,useState} from 'react';
import {createRoot,Root} from 'react-dom/client';
import {createPortal} from 'react-dom';
import {Download,ExternalLink,Monitor,Play,ScanEye,Square} from 'lucide-react';
import {api,download,fetchApi,Rules,Snapshot} from './api';
import {ScreenShare,captureScreenFrame,screenSharingError} from './screen-sharing';
import {LiveVideoLoop} from './live-loop';
import {DemoVideoSource} from './demo-source';
import {getLanguage,t} from './i18n';
import {localize} from './localize';
import './live.css';

const actions:Record<string,string>={hit:'Hit',stand:'Stand',double:'Double',split:'Split',surrender:'Surrender',continue:'Continue',insurance:'Insurance',decline_insurance:'Decline insurance'};
const percent=(value:unknown)=>typeof value==='number'?(value*100).toFixed(1)+'%':'—';
const number=(value:unknown,d=2)=>typeof value==='number'?value.toFixed(d):'—';

export function LiveAdvisor({report,stale,compact=false}:{report:any;stale:boolean;compact?:boolean}){
 const decision=!stale?report?.decision:null,best=decision?.best_action,row=decision?.actions?.[best];
 return localize(<section className={'live-advisor '+(compact?'compact':'')} aria-label="Probability estimates">
  <div className="advisor-heading"><span className={'status-dot '+(decision?'ok':'')}/><span>{stale?'Decision stale — waiting for fresh video':decision?'Recommended action':'Waiting for stable cards'}</span></div>
  <h2>{best?actions[best]||best:'Observe → verify → decide'}</h2>
  <p className="advisor-cards"><span>Player <b>{report?.player?.join(' · ')||'—'}</b></span><span>Dealer <b>{report?.dealer?.join(' · ')||'—'}</b></span></p>
  <div className="probability-grid"><div><span>Win</span><strong>{percent(row?.win)}</strong></div><div><span>Push</span><strong>{percent(row?.push)}</strong></div><div><span>Loss</span><strong>{percent(row?.loss)}</strong></div></div>
  {row&&<><div className="advisor-ev"><span>Estimated EV</span><b>{number(row.ev,4)}</b></div><p className="probability-note">95% confidence interval: {percent(row.win_ci95?.[0])} – {percent(row.win_ci95?.[1])}<br/>{decision.samples_per_action} simulated outcomes per action · {decision.exact?'Exact':'Monte Carlo estimate'}</p><p className="edge-note">{row.ev>0?'Positive estimated EV':'No positive EV detected'}{!decision.ranking_resolved&&' · '+t('No clear ranking')}</p></>}
  {decision?.insurance_blackjack_probability!==undefined&&<p>Dealer blackjack: {percent(decision.insurance_blackjack_probability)} · Insurance EV: {number(decision.insurance_ev,4)}</p>}
  <div className="advisor-count"><span>Observed cards <b>{report?.observed_cards??0}</b></span><span>Running count <b>{report?.running_count??0}</b></span><span>True count <b>{number(report?.true_count)}</b></span></div>
  <p className="probability-note">{report?.count_scope==='from declared fresh shoe'?'Fresh shoe declared':'Partial observed count'}</p>
  {!decision&&<p className="gate-note" role="status">{stale?'Advice is hidden until new video arrives.':report?.gate?.reasons?.[0]||'Select a video source to begin.'}</p>}
  {!compact&&decision?.actions&&<div className="live-action-table"><div><b>Action</b><b>EV</b><b>Win</b><b>Push</b><b>Loss</b></div>{Object.entries(decision.actions).map(([name,value]:[string,any])=><div key={name} className={name===best?'best':''}><span>{actions[name]||name}</span><span>{number(value.ev,4)}</span><span>{percent(value.win)}</span><span>{percent(value.push)}</span><span>{percent(value.loss)}</span></div>)}</div>}
 </section>);
}

export default function LiveVision({rules,connected}:{rules:Rules;connected:boolean}){
 const video=useRef<HTMLVideoElement>(null),owner=useRef(new ScreenShare()),demo=useRef<DemoVideoSource|null>(null),loop=useRef<LiveVideoLoop|null>(null);
 const identity=useRef<string|null>(null),generation=useRef(0),sourceGeneration=useRef(0),mounted=useRef(true),abort=useRef<AbortController|null>(null);
 const [stream,setStream]=useState<MediaStream|null>(null),[source,setSource]=useState(''),[pending,setPending]=useState(false),[observing,setObserving]=useState(false),[error,setError]=useState('');
 const [report,setReport]=useState<any>(null),[lastSeen,setLastSeen]=useState(0),[stale,setStale]=useState(true),[corners,setCorners]=useState<number[][]>([]),[selecting,setSelecting]=useState(false);
 const [samples,setSamples]=useState(1500),[fresh,setFresh]=useState(false),[manualTurn,setManualTurn]=useState(false),[bot,setBot]=useState(true),[demoState,setDemoState]=useState<Snapshot|null>(null);
 const [metrics,setMetrics]=useState({sent:0,skipped:0,latency:0}),[advisorOpen,setAdvisorOpen]=useState(false),[inlineAdvisor,setInlineAdvisor]=useState(false),[advisorOpening,setAdvisorOpening]=useState(false),floating=useRef<{window:Window;root:Root}|null>(null),advisorGeneration=useRef(0);
 const language=getLanguage();

 const stopObserver=()=>{
  generation.current++;loop.current?.stop();loop.current=null;abort.current?.abort();abort.current=null;
  const old=identity.current;identity.current=null;if(old)void fetchApi('/live/'+old,{method:'DELETE'}).catch(()=>{});
  if(mounted.current){setObserving(false);setReport(null);setStale(true);setLastSeen(0)}
 };
 const stop=()=>{sourceGeneration.current++;stopObserver();owner.current.stop();demo.current?.dispose();demo.current=null;if(mounted.current){setStream(null);setPending(false);setSource('');setDemoState(null)}};
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;advisorGeneration.current++;stop();const previous=floating.current;floating.current=null;previous?.root.unmount();previous?.window.close()}},[]);
 useEffect(()=>{if(!connected)stopObserver()},[connected]);
 useEffect(()=>{const timer=setInterval(()=>setStale(!lastSeen||performance.now()-lastSeen>2200),200);return()=>clearInterval(timer)},[lastSeen]);
 useEffect(()=>{const target=floating.current;if(target&&!target.window.closed){target.window.document.documentElement.lang=language;target.root.render(localize(<LiveAdvisor report={report} stale={stale} compact/>))}},[report,stale,language]);

 const startObserver=async()=>{
  stopObserver();if(!video.current||!stream||!connected)return;
  if(corners.length!==0&&corners.length!==4){setError('Select all four table corners before observing.');return}
  const attempt=generation.current;setError('');setPending(true);
  try{
   const configuration=await api('/live',{rules,samples,corners:corners.length===4?corners:null,fresh_shoe:source==='demo'||fresh,manual_turn:manualTurn});
   if(!mounted.current||attempt!==generation.current){void fetchApi('/live/'+configuration.stream_id,{method:'DELETE'});return}
   identity.current=configuration.stream_id;setObserving(true);
   const target=video.current!;const id=configuration.stream_id;
   loop.current=new LiveVideoLoop(target,async(sequence)=>{
    const began=performance.now(),controller=new AbortController();abort.current=controller;
    const timeout=setTimeout(()=>controller.abort(),6000);
    try{
     const image=await captureScreenFrame(target);
     if(attempt!==generation.current)return;
     const response=await fetchApi('/live/'+id+'/frame?sequence='+sequence+'&timestamp='+(began/1000),{method:'POST',body:image,signal:controller.signal,headers:{'Content-Type':'image/png'}});
     const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'Video processing failed.');
     if(!mounted.current||attempt!==generation.current)return;
     setReport(value);setLastSeen(began);setStale(performance.now()-began>2200);setError('');setMetrics({sent:sequence+1,skipped:loop.current?.skipped||0,latency:performance.now()-began});
    }finally{clearTimeout(timeout)}
   },e=>{setReport(null);setStale(true);setError(e instanceof Error&&e.name==='AbortError'?'Video processing timed out. Waiting for a fresh observation.':String(e instanceof Error?e.message:e))});
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
  stop();setError('');setCorners([]);setSelecting(false);setPending(true);const attempt=sourceGeneration.current;
  try{
   let next:MediaStream|null;
   if(kind==='screen')next=await owner.current.start();
   else{const source=new DemoVideoSource(rules,value=>{if(mounted.current&&attempt===sourceGeneration.current)setDemoState(value)});demo.current=source;next=await source.start();setBot(true)}
   if(!mounted.current||attempt!==sourceGeneration.current){next?.getTracks().forEach(track=>track.stop());return}
   if(next){setSource(kind);setStream(next)}
  }catch(e){if(mounted.current&&attempt===sourceGeneration.current)setError(screenSharingError(e))}
  finally{if(mounted.current&&attempt===sourceGeneration.current)setPending(false)}
 };
 const closeAdvisor=()=>{advisorGeneration.current++;const previous=floating.current;floating.current=null;previous?.root.unmount();previous?.window.close();setAdvisorOpen(false);setInlineAdvisor(false);setAdvisorOpening(false)};
 const openAdvisor=async()=>{
  closeAdvisor();const attempt=advisorGeneration.current;setInlineAdvisor(true);setAdvisorOpen(true);setAdvisorOpening(true);
  try{
   const pip=(window as Window&{documentPictureInPicture?:{requestWindow:(options:{width:number;height:number})=>Promise<Window>}}).documentPictureInPicture;
   let win:Window|null=null;
   if(pip){let expired=false;let timer:ReturnType<typeof setTimeout>|undefined;const requested=pip.requestWindow({width:390,height:590});
    void requested.then(value=>{if(expired||attempt!==advisorGeneration.current||!mounted.current)value.close()}).catch(()=>{});
    try{win=await Promise.race([requested,new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(new Error('Picture-in-Picture unavailable')),1800)})])}catch{expired=true}finally{clearTimeout(timer)}
   }
   if(!mounted.current||attempt!==advisorGeneration.current){win?.close();return}
   if(!win){setInlineAdvisor(true);setAdvisorOpen(true);setError('Advisor is shown in this page. Use Chrome or Edge for a separate always-on-top window.');return}
   win.document.title='Blackjack Vision Lab · Live advisor';win.document.documentElement.lang=language;
   win.document.querySelectorAll('style,link[rel="stylesheet"]').forEach(node=>node.remove());
   document.querySelectorAll('style,link[rel="stylesheet"]').forEach(node=>{const clone=node.cloneNode(true) as HTMLElement;if(node instanceof HTMLLinkElement)clone.setAttribute('href',node.href);win.document.head.appendChild(clone)});
   win.document.body.className='advisor-window';const mount=win.document.createElement('div');win.document.body.replaceChildren(mount);
   const root=createRoot(mount);floating.current={window:win,root};setInlineAdvisor(false);setAdvisorOpen(true);root.render(localize(<LiveAdvisor report={report} stale={stale} compact/>));
   win.addEventListener('pagehide',()=>{if(floating.current?.window===win){floating.current=null;root.unmount();if(mounted.current){setInlineAdvisor(true);setAdvisorOpen(true)}}},{once:true});
  }catch(e){if(mounted.current&&attempt===advisorGeneration.current){setInlineAdvisor(true);setAdvisorOpen(true);setError(e instanceof Error?e.message:String(e))}}
  finally{if(mounted.current&&attempt===advisorGeneration.current)setAdvisorOpening(false)}
 };
 const openBrowser=async()=>{try{await api('/live/browser',{});setError('Opened the local app in your browser. Keep the desktop app open while sharing.')}catch(e){setError(e instanceof Error?e.message:String(e))}};
 return localize(<div className="live-workspace">
  <section className="panel live-controls"><div><div className="section-label">CONTINUOUS SCREEN VIDEO</div><h2>Share once. Follow the whole game.</h2><p>Choose a screen, window or browser tab. Observation continues automatically; no image capture button is needed.</p></div><div className="live-buttons">
   <button className="button primary" disabled={pending||!connected} onClick={()=>void start('screen')}><Monitor size={16}/>Share screen</button>
   <button className="button secondary" disabled={pending||!connected} onClick={()=>void start('demo')}><Play size={16}/>Run lab demo</button>
   {stream&&<button className="button secondary" onClick={stop}><Square size={14}/>Stop video</button>}
   {pending&&<button className="button secondary" onClick={stop}>Cancel</button>}
   <button className="button secondary" onClick={()=>{if(advisorOpen)closeAdvisor();else{setInlineAdvisor(true);setAdvisorOpen(true)}}}><ExternalLink size={14}/>{advisorOpen?'Close advisor':'Floating advisor'}</button>
   {advisorOpen&&<button className="button secondary" disabled={advisorOpening} onClick={()=>void openAdvisor()}>{advisorOpening?'Opening advisor…':'Pop out advisor'}</button>}
   <a className="button secondary" href="/?simulator=1" target="_blank" rel="noopener">Open simulator window</a>
  </div></section>
  {error&&<p className="tool-error live-error" role="alert">{error}</p>}
  <div className="live-columns"><section className="panel live-video-panel"><div className="panel-header"><h2><ScanEye size={17}/>{source==='demo'?'Lab video demo':'Screen video'}</h2><span className="badge" role="status">{observing?'Video connected':stream?'Video paused':'Waiting for video'}</span></div>
   {stream?<div className={'live-video-wrap '+(selecting?'selecting':'')} onClick={e=>{if(!selecting||corners.length>=4)return;const b=e.currentTarget.getBoundingClientRect();setCorners(previous=>[...previous,[(e.clientX-b.left)/b.width,(e.clientY-b.top)/b.height]])}}>
    <video ref={video} muted autoPlay playsInline aria-label="Continuous shared video" onLoadedData={()=>void startObserver()}/>
    <svg className="live-detections" viewBox={'0 0 '+(video.current?.videoWidth||960)+' '+(video.current?.videoHeight||600)} aria-label="Live recognized cards">{corners.length===0&&(report?.detections||[]).map((d:any,i:number)=>{const [x,y,w,h]=d.bbox;return <g key={i}><rect x={x} y={y} width={w} height={h}/><text x={x+3} y={Math.max(18,y-7)}>{d.face_down?'BACK':d.rank+' '+d.suit}</text></g>})}</svg>
    {corners.map((c,i)=><span className="live-corner" key={i} style={{left:c[0]*100+'%',top:c[1]*100+'%'}}>{i+1}</span>)}
   </div>:<div className="live-placeholder"><Monitor size={38}/><h3>Give the lab a live video source.</h3><p>Share your simulation, or run the lab demo to test video → recognition → tracking → advice.</p></div>}
   <div className="live-config"><label>Samples per action<select disabled={observing||pending} value={samples} onChange={e=>setSamples(Number(e.target.value))}><option value="500">500 · fast</option><option value="1500">1,500 · balanced</option><option value="5000">5,000 · precise</option></select></label><label><input type="checkbox" disabled={observing||pending} checked={fresh} onChange={e=>setFresh(e.target.checked)}/>Observe from a new shoe</label><label><input type="checkbox" disabled={observing||pending} checked={manualTurn} onChange={e=>setManualTurn(e.target.checked)}/>Player turn (manual layout)</label>
    {stream&&<button className="button secondary" onClick={()=>{if(observing)stopObserver();else void startObserver()}} disabled={pending}>{observing?'Stop observing':'Start observing'}</button>}
   </div>
   {stream&&<div className="live-calibration"><button className="text-button" onClick={()=>{stopObserver();setSelecting(v=>!v);setCorners([])}}>Table calibration</button><span>Selected corners: {corners.length} / 4</span><button className="text-button" onClick={()=>{stopObserver();setCorners([]);setSelecting(false)}}>Clear corners</button><button className="button secondary" disabled={corners.length!==4||pending} onClick={()=>{setSelecting(false);void startObserver()}}>Apply calibration</button><p>For a full screen, select the table corners: top left, top right, bottom right, bottom left. Keep its position fixed while observing.</p></div>}
   {source==='demo'&&demoState&&<div className="live-demo-actions"><button className="button secondary" onClick={()=>{demo.current?.setBot(!bot);setBot(v=>!v)}}>{bot?'Pause bot':'Resume bot'}</button>{demoState.available_actions.map(action=><button key={action} className="button secondary" onClick={()=>void demo.current?.action(action).catch(e=>setError(e.message))}>{action==='deal'?'Deal':action==='shuffle'?'New shoe':actions[action]||action}</button>)}<span>Round {demoState.round_id} · {demoState.phase}</span></div>}
   <div className="live-metrics"><span>Video processing <b>{number(metrics.latency,0)} ms</b></span><span>Distinct observations <b>{metrics.sent}</b></span><span>Skipped while busy <b>{metrics.skipped}</b></span></div>
   <p className="panel-caption">Processing runs locally. The preview is video; the analysis samples it automatically with one upload in flight. Guidance expires when the video stops updating.</p>
   <details className="live-details"><summary>Recognition scope and probability method</summary><p>The included detector is validated for lab card artwork. Other artwork needs a trained detector and a separate test. Counts cover only what the video has actually observed. Select a new shoe before relying on a full-shoe count.</p><p>Win, push and loss describe net profit of the active hand, including any new splits. Existing other hands are excluded. EV estimates use finite-pool Monte Carlo with generated basic continuation; sampling intervals do not measure perception error.</p></details>
   <p className="panel-caption">Display sharing needs Chrome or Edge on localhost. <button className="text-button" onClick={()=>void openBrowser()}>Open in default browser</button></p>
  </section><LiveAdvisor report={report} stale={stale}/></div>
  {report&&<div className="live-export"><button className="button secondary" onClick={()=>download('live-observation.json',report)}><Download size={14}/>Export observation</button><button className="button secondary" onClick={()=>identity.current&&void api('/live/'+identity.current+'/events').then(value=>download('live-events.json',value))}><Download size={14}/>Export observed events</button></div>}
  {inlineAdvisor&&createPortal(localize(<aside className="inline-live-advisor" aria-label="Floating live advisor"><button className="text-button" onClick={closeAdvisor}>Close advisor</button><LiveAdvisor report={report} stale={stale} compact/></aside>),document.body)}
 </div>);
}
