import {compactAdvisor} from './compact-advisor';
import './compact-advisor.css';

export default function CompactAdvisor({report,stale,ageMs}:{report:any;stale:boolean;ageMs?:number}){
 const view=compactAdvisor(report,stale);
 return <section className={'mini-advisor '+view.status.toLowerCase()} aria-label="Compact live advisor">
  <div className="mini-evidence"><span className="mini-status" role="status" title="R1: current hand observation"><i/>{view.status}</span><small>{typeof ageMs==='number'&&Number.isFinite(ageMs)?Math.max(0,ageMs/1000).toFixed(1)+' s':'—'}</small></div>
  <div className="mini-hand"><strong>{view.total??'—'}{view.soft&&<small>soft</small>}</strong><span className="mini-cards" title={view.player.join(' · ')}>Player {view.player.join(' · ')||'—'}{view.hasAce&&<small>A = 1 / 11{view.soft?' · '+view.hard+' or '+view.total:''}</small>}</span><span className="mini-dealer">vs <b>{view.dealer.join(' · ')||'—'}</b></span></div>
  <div className={'mini-action '+(view.action?'ready':'waiting')} aria-live="polite">{view.display}</div>
  {!view.action&&<div className="mini-reason" title={view.reason}>{view.reason}</div>}
  <div className="mini-count" title="R2: session count, separate from current-hand advice">{view.count}</div>
 </section>;
}
