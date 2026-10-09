import {useEffect,useState} from 'react';
import {api,download} from './api';
import {localize} from './localize';

export default function VisionMatrix(){
 const [data,setData]=useState<any>(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;void api('/vision/experiments').then(value=>{if(active)setData(value)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[]);
 return localize(<section className="panel">
  <div className="section-label">VISION EXPERIMENT FUNNEL</div>
  <h2>Evidence before promotion.</h2>
  <p>Each stage keeps its baseline, alternatives, status and measured failures. Private development screenshots remain local. Repeated previews are the same session; monitor photos are diagnostic.</p>
  {error&&<p role="alert">{error}</p>}
  {data&&<>
   <p>Running package: <b>{data.runtime.package_version}</b> · Detector: <b>{data.runtime.detector_version}</b><br/>
    Candidate commit: <code>{data.runtime.commit?.slice(0,12)||"unavailable"}</code>{data.runtime.working_tree_dirty?" · local changes":""}<br/>
    Content fingerprint: <code>{data.runtime.source_fingerprint.slice(0,16)}</code><br/>{data.runtime.publication}<br/>
    Frozen reference: desktop {data.baseline.version} · {data.baseline.commit.slice(0,12)}</p>
   <button className="button secondary" onClick={()=>download('vision-experiments.json',data)}>Export experiment matrix</button>
   <div className="table-scroll"><table><thead><tr><th>Stage</th><th>Candidate</th><th>Status</th><th>Finding / next proof</th></tr></thead>
    <tbody>{data.stages.map((stage:any)=><tr key={stage.id}><td>{stage.stage}</td><td>{stage.candidate}</td><td>{stage.status}</td><td>{stage.finding}</td></tr>)}</tbody>
   </table></div>
   {[['Historical development comparison',data.comparison],['Presence and usable-state follow-up',data.latest_comparison]].map(([title,comparison]:any)=>comparison&&<div key={title}>
    <h3>{title}</h3><p>{comparison.scope}</p>
    <div className="table-scroll"><table><thead><tr><th>Profile</th><th>Matched correct ranks</th><th>Rank inventory intersection</th><th>Suits: correct / wrong / unknown / missed</th><th>Objects: missed / extra</th><th>Correctly usable stills</th><th>Offline p95</th></tr></thead>
     <tbody>{Object.entries(comparison.aggregates).map(([name,result]:[string,any])=><tr key={name}>
      <td>{name}</td><td>{result.rank_correct_including_misses} / {result.visible_cards}</td>
      <td>{result.correct_zone_ranks} / {result.visible_cards}</td>
      <td>{result.suits_supported===false?'Not supported':result.outcomes?.suit?['correct','wrong','unknown','missed'].map(k=>result.outcomes.suit[k]).join(' / '):'Not measured'}</td>
      <td>{result.presence_outcomes?`${result.presence_outcomes.missed} / ${result.presence_outcomes.extra}`:'Not measured'}</td>
      <td>{result.state_usefulness?`${result.state_usefulness.correctly_usable} / ${result.state_usefulness.stills}`:'Not measured'}</td>
      <td>{result.offline_ms_p95.toFixed(0)} ms</td>
     </tr>)}</tbody>
    </table></div>
    <p>Repeated stills and offline timing do not measure independent sessions, first stable video latency or count reconstruction.</p>
    {comparison.full_card_geometry_warning&&<p>{comparison.full_card_geometry_warning}</p>}
   </div>)}
   {data.learning_checks&&<>
    <h3>YOLO learning diagnostics</h3>
    <p>Train examples are deliberately reused to check memorization. Passing this check would permit a comparison; it would not prove generalization.</p>
    <div className="table-scroll"><table><thead><tr><th>Initialization / task</th><th>Fixed .50 gate</th><th>Development observations</th><th>Decision</th></tr></thead>
     <tbody>{data.learning_checks.map((check:any)=><tr key={check.id}><td>{check.initialization} · {check.task}</td><td>{check.learning_gate?'Passed':'Not passed'}</td><td>{check.finding}</td><td>{check.decision}</td></tr>)}</tbody>
    </table></div>
   </>}
   {data.own_development_sessions&&<>
    <h3>Own-renderer development sessions</h3>
    <p>These are synthetic sequences with simulated manual turn confirmation. Repeated observations are not unique card exposures or new provider recordings.</p>
    <div className="table-scroll"><table><thead><tr><th>Seed</th><th>Usable decision states</th><th>Correct face observations</th><th>Inventory L1 error</th><th>Observed RC error</th></tr></thead>
     <tbody>{data.own_development_sessions.sessions.map((s:any)=><tr key={s.seed}><td>{s.seed}</td><td>{s.correctly_usable_decision_states} / {s.decision_states}</td><td>{s.ranks_correct} / {s.visible_faces}</td><td>{s.final_inventory_l1_error}</td><td>{s.final_observed_rc_error}</td></tr>)}</tbody>
    </table></div>
    <p>Complete count remains unverified for this research profile.</p>
   </>}
  </>}
 </section>);
}
