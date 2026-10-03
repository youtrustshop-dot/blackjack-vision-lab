import {useEffect,useRef,useState} from 'react';
import {api,defaultRules,fetchApi,Snapshot} from './api';
import LanguageSelector from './LanguageSelector';
import {getLanguage} from './i18n';
import {localize} from './localize';
import './live.css';
import {readRules,saveRules} from './preferences';
import {Setup,ReuseConfiguration} from './Setup';
import {LiveAdvisor} from './LiveVision';
const actionNames:Record<string,string>={hit:'Hit',stand:'Stand',double:'Double',split:'Split',surrender:'Surrender',insurance:'Insurance',decline_insurance:'Decline insurance',continue:'Continue',deal:'Deal',shuffle:'New shoe'};
export default function SimulatorWindow(){
 const [state,setState]=useState<Snapshot|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[bot,setBot]=useState(false),[seed,setSeed]=useState(42),[,setLanguage]=useState(getLanguage());
 const [confirmReset,setConfirmReset]=useState(false);
 const [rules,setRules]=useState(readRules),[setup,setSetup]=useState(false);
 const alive=useRef(true),identity=useRef(''),working=useRef(false),generation=useRef(0);
 const create=async(nextRules=rules)=>{const attempt=++generation.current;setBusy(true);try{const next=await api<Snapshot>('/sessions',{seed,rules:nextRules});if(!alive.current||attempt!==generation.current){void fetchApi('/sessions/'+next.session_id,{method:'DELETE'});return}const old=identity.current;identity.current=next.session_id;setState(next);if(old)void fetchApi('/sessions/'+old,{method:'DELETE'})}catch(e){setError(e instanceof Error?e.message:String(e))}finally{if(alive.current)setBusy(false)}};
 useEffect(()=>{alive.current=true;document.documentElement.lang=getLanguage();void create();return()=>{alive.current=false;generation.current++;if(identity.current)void fetchApi('/sessions/'+identity.current,{method:'DELETE'})}},[]);
 const act=async(action:string)=>{if(!identity.current||working.current)return;working.current=true;setBusy(true);setError('');try{const result=await api<Snapshot>('/sessions/'+identity.current+(action==='bot'?'/bot-step':action==='deal'?'/deal':'/action'),action==='bot'||action==='deal'?{}:{action});if(alive.current)setState(result)}catch(e){if(alive.current){setError(e instanceof Error?e.message:String(e));setBot(false)}}finally{working.current=false;if(alive.current)setBusy(false)}};
 useEffect(()=>{if(!bot)return;const timer=setInterval(()=>void act('bot'),4000);return()=>clearInterval(timer)},[bot]);
 return localize(<div className="simulator-only"><LanguageSelector onChange={setLanguage}/><div className="section-label">BLACKJACK VISION LAB / VIDEO SOURCE</div><h1>A table your live advisor can watch.</h1><p>Share this window from Live vision, select the four table corners, and play manually or start the bot. The advisor reads the visible video, including round labels and buttons.</p>{error&&<p role="alert" className="tool-error">{error}</p>}
  {state?<img src={'/api/sessions/'+state.session_id+'/frame?theme=black&live_context=true&v='+state.events_count} alt="Visible blackjack simulation table"/>:<p>Starting simulator…</p>}
  <div className="live-demo-actions"><button className="button primary" disabled={busy} onClick={()=>setBot(v=>!v)}>{bot?'Pause bot':'Resume bot'}</button>{state?.available_actions.map(action=><button key={action} className="button secondary" disabled={busy} onClick={()=>void act(action)}>{actionNames[action]||action}</button>)}</div>
  <div className="live-demo-actions"><label>Seed <input type="number" value={seed} onChange={e=>setSeed(Number(e.target.value))}/></label><button className="button secondary" disabled={busy} onClick={()=>{setBot(false);if(localStorage.getItem('bjlab.reuseRules')==='yes')void create();else setConfirmReset(true)}}>New session</button><button className="button secondary" onClick={()=>{setBot(false);setSetup(true)}}>Configure</button><span>{rules.decks} decks · {rules.hit_soft17?'H17':'S17'} · Round {state?.round_id||0} · Net profit {state?.total_profit.toFixed(2)||'0.00'} units</span></div>
 {state?.advice&&<LiveAdvisor report={{advice:state.advice,player:state.hands[state.active_hand||0]?.cards.map(c=>c.rank),dealer:state.dealer.cards.filter(c=>!c.face_down).map(c=>c.rank),observed_cards:state.shoe.seen,running_count:state.shoe.running_count,true_count:state.shoe.true_count}} stale={false} compact/>}
 {confirmReset&&<ReuseConfiguration rules={rules} onClose={()=>setConfirmReset(false)} onConfirm={()=>{setConfirmReset(false);void create()}}/>}
 {setup&&<Setup rules={rules} onClose={()=>setSetup(false)} onSave={value=>{setRules(value);saveRules(value);setSetup(false);void create(value)}}/>}
 <p className="help-note">Analysis and education only. Not financial advice. No guaranteed outcomes.</p>
 </div>);
}
