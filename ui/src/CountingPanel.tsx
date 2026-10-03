import {localize} from './localize';
import {useEffect,useState} from 'react';
import {Check,Download,Layers} from 'lucide-react';
import {api,download,Snapshot} from './api';
const f=(value:unknown)=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(3):'—';
export default function CountingPanel({session}:{session:Snapshot|null}){
 const [rounding,setRounding]=useState('truncate'),[cards,setCards]=useState<string[]>([]),[report,setReport]=useState<any>(null),[custom,setCustom]=useState<any>(null),[error,setError]=useState('');
 const [name,setName]=useState('My counting system'),[tags,setTags]=useState('-1,1,1,1,1,1,0,0,0,-1'),[balanced,setBalanced]=useState(true),[busy,setBusy]=useState(false);
 useEffect(()=>{let live=true;setError('');setReport(null);setCustom(null);if(!session)return;
  api('/sessions/'+session.session_id+'/events').then(async result=>{
   let observed:string[]=[];const identities=new Set<string>();
   for(const event of result.events){if(['shoe_started','shoe_fixture'].includes(event.kind)){observed=[];identities.clear()}else if(event.kind==='card_exposed'){const c=event.payload.card;if(!identities.has(c.id)){observed.push(c.rank);identities.add(c.id)}}}
   const value=await api('/counting/compare',{cards:observed,decks:session.rules.decks,cards_remaining:session.shoe.remaining||undefined,rounding});
   if(live){setCards(observed);setReport(value)}
  }).catch(e=>{if(live)setError(e.message)});return()=>{live=false};
 },[session?.session_id,session?.events_count,rounding]);
 const evaluate=async()=>{if(!session)return;setBusy(true);setError('');try{
  const parsed=tags.split(',').map(v=>Number(v.trim()));if(parsed.length!==10||tags.split(',').some(v=>!v.trim())||parsed.some(v=>!Number.isFinite(v)))throw new Error('Servono dieci tag numerici, da Asso a 10, separati da virgole.');
  setCustom(await api('/counting/custom',{name,tags:parsed,balanced,cards,decks:session.rules.decks,cards_remaining:session.shoe.remaining||undefined,rounding}));
 }catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}};
 return localize(<><section className="panel"><div className="panel-header"><h2><Layers size={16}/>Sistemi sulla stessa sequenza osservata</h2><button className="button secondary" disabled={!report} onClick={()=>download('counting-comparison.json',report)}><Download size={14}/>Esporta</button></div>
 <div className="counting-intro"><p>{cards.length} carte esposte nello shoe corrente. Le carte coperte entrano nel conteggio quando vengono rivelate.</p><label>Arrotondamento TC<select value={rounding} onChange={e=>setRounding(e.target.value)}><option value="truncate">Troncamento</option><option value="floor">Floor</option><option value="nearest">Intero più vicino</option><option value="none">Nessuno</option></select></label></div>
 {error&&<p className="tool-error" role="alert">{error}</p>}
 <div className="table-scroll"><table className="counting-table"><thead><tr><th>Sistema</th><th>Running count</th><th>True count</th><th>TC arrotondato</th><th>Normalizzazione</th></tr></thead><tbody>{Object.entries(report?.systems||{}).map(([system,r]:[string,any])=><tr key={system}><td>{system}</td><td>{f(r.running_count)}</td><td>{f(r.true_count)}</td><td>{f(r.rounded_true_count)}</td><td>{r.balanced?'Mazzi rimasti':'Running count'}</td></tr>)}</tbody></table></div>
 <p className="panel-caption">Il denominatore usa le carte fisiche rimaste dichiarate dal simulatore. Nella percezione questa quantità deve essere stimata separatamente.</p></section>
 <section className="panel custom-counter"><div className="panel-header"><h2>Definisci un sistema personalizzato</h2></div><div className="tool-grid"><div><label>Nome<input value={name} onChange={e=>setName(e.target.value)}/></label><label>Tag: A, 2, 3, 4, 5, 6, 7, 8, 9, 10<input value={tags} onChange={e=>setTags(e.target.value)}/></label><label className="counter-balanced"><input type="checkbox" checked={balanced} onChange={e=>setBalanced(e.target.checked)}/>Sistema bilanciato</label><button className="button primary" disabled={!session||busy} onClick={()=>void evaluate()}><Check size={14}/>Valida e calcola</button></div><div>{custom?<pre>{JSON.stringify(custom,null,2)}</pre>:<p>I tag vengono validati rispetto alla composizione di un mazzo. Il risultato usa gli stessi eventi esposti del confronto.</p>}</div></div></section></>);
}
