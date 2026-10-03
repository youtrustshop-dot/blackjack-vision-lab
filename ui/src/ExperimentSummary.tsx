const names:Record<string,string>={basic:'Basic · replacement',hilo:'Hi-Lo · chart',composition:'Composizione'};
const f=(value:unknown,d=4)=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(d):'—';
export default function ExperimentSummary({result}:{result:any}){
 const rows=Object.entries(result.results||{}) as [string,any][];
 const bounds=rows.flatMap(([,value])=>value.ci95||[value.mean]);
 const low=Math.min(-.01,...bounds),high=Math.max(.01,...bounds),span=high-low||1;
 const position=(value:number)=>(value-low)/span*100+'%';
 return <section className="panel policy-summary"><div className="panel-header"><h2>EV misurato & incertezza</h2><span className="badge">{result.completed_rounds} / {result.requested_rounds} ROUND</span></div>
 <p className="panel-caption">Profitto netto medio per unità di puntata iniziale. Gli intervalli descrivono il campionamento fra batch indipendenti.</p>
 {result.status!=='complete'&&<p className="tool-error">Il budget di tempo è terminato: il report usa soltanto i round effettivamente completati.</p>}
 <div className="policy-cards">{rows.map(([policy,value])=><div className="policy-card" key={policy}><h3>{names[policy]||policy}</h3><strong>{f(value.mean)}</strong><span>IC 95%: {value.ci95?f(value.ci95[0])+' … '+f(value.ci95[1]):'non disponibile'}</span><div className="interval-chart"><i className="interval-zero" style={{left:position(0)}}/>{value.ci95&&<i className="interval-range" style={{left:position(value.ci95[0]),width:(value.ci95[1]-value.ci95[0])/span*100+'%'}}/>}<i className="interval-point" style={{left:position(value.mean)}}/></div><small>{value.independent_batches} batch · {value.rounds} round<br/>{value.fallback_decisions||0} decisioni con fallback</small></div>)}</div>
 {result.comparisons?.length>0&&<div className="paired-comparisons"><div className="section-label">DIFFERENZE TRA POLICIES · BATCH ABBINATI</div>{result.comparisons.map((comparison:any,i:number)=><p key={i}><b>{names[comparison.first]||comparison.first} − {names[comparison.second]||comparison.second}</b><span>{f(comparison.difference.mean)} · IC 95% {comparison.difference.ci95?comparison.difference.ci95.map((x:number)=>f(x)).join(' … '):'non disponibile'}</span></p>)}</div>}
 </section>;
}
