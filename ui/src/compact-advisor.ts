const labels:Record<string,string>={hit:'HIT',stand:'STAND',double:'DOUBLE',split:'SPLIT',surrender:'SURRENDER',insurance:'INSURANCE',decline_insurance:'NO INSURANCE'};

/** A compact view never certifies the session from a usable current hand. */
export function compactAdvisor(report:any,stale:boolean){
 const cards=(value:unknown):string[]=>Array.isArray(value)?value.filter((card:unknown)=>typeof card==='string'):[];
 const player=cards(report?.player),dealer=cards(report?.dealer);
 const values=player.map(card=>card==='A'?1:['10','T','J','Q','K'].includes(card)?10:Number(card));
 const hard=values.reduce((sum,value)=>sum+value,0),soft=values.includes(1)&&hard+10<=21;
 const ranks=['A','2','3','4','5','6','7','8','9','10','T','J','Q','K'];
 const playerKnown=player.length>=2&&player.every(card=>ranks.includes(card));
 const known=playerKnown&&dealer.length===1&&ranks.includes(dealer[0]);
 const actionKey=report?.advice?.best_action||report?.decision?.best_action;
 const action=!stale&&report?.gate?.solver_allowed===true&&known?labels[actionKey]||null:null;
 const status=stale?'STALE':action?'LIVE':'UNCERTAIN';
 const idle=['waiting','dealing','dealer','settled'].includes(report?.phase);
 const reason=stale?'Refresh the source':report?.phase==='settled'?'Hand complete':report?.gate?.reasons?.[0]||'Waiting for a stable hand';
 const countCurrent=!stale&&report?.count_reliable===true&&Number.isFinite(report?.true_count);
 return {player,dealer,total:playerKnown?hard+(soft?10:0):null,soft,hard,
  hasAce:player.includes('A'),action,status,reason,display:action||(stale?'STALE':idle?'WAIT':'CHECK TABLE'),
  count:countCurrent?'R2 · TC '+(report.true_count>=0?'+':'')+report.true_count.toFixed(2):'R2 · COUNT UNVERIFIED'};
}

/** The native route, source snapshot and selected table must agree. */
export function advisorSnapshotCurrent(value:any,host:any,stream:string){
 const source=value?.source_id,report=value?.report;
 const stateMatches=typeof report?.state_id==='string'?report.state_id.startsWith(source+':'):
  report?.state_id===null&&report?.gate?.solver_allowed===false&&!report?.advice&&!report?.decision;
 return Boolean(host?.available&&host.stream_id===stream&&typeof source==='string'&&source.length&&
  host.tables?.some((table:any)=>table.stream_id===stream&&table.source_id===source)&&
  report?.source_id===source&&stateMatches&&value.stale===false);
}
