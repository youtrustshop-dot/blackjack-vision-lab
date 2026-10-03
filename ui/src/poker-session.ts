export class PokerSession {
 private candidate='';private hits=0;private previous:any=null;round=1;events:any[]=[];
 reset(){this.candidate='';this.hits=0;this.previous=null;this.round++;this.events.push({kind:'NEW_HAND',round:this.round})}
 observe(report:any,timestamp:number,preflopConfirmed=false,singleImage=false){
  const token=JSON.stringify([report.hole,report.board]);
  this.hits=token===this.candidate?this.hits+1:1;this.candidate=token;
  const reasons=[...(report.gate?.reasons||[])];
  if(!singleImage&&this.hits<3)reasons.push('Waiting for three stable card observations.');
  if(report.board?.length===0&&!preflopConfirmed)reasons.push('Confirm preflop explicitly before using an empty board.');
  if(this.previous&&JSON.stringify(report.hole)===JSON.stringify(this.previous.hole)){
   const prior=this.previous.board||[];
   if(report.board.length<prior.length||!prior.every((c:string,i:number)=>report.board[i]===c))reasons.push('The board changed incompatibly. Confirm a new hand or recalibrate.');
  }
  if(!reasons.length){
   if(this.previous&&JSON.stringify(report.hole)!==JSON.stringify(this.previous.hole)){this.round++;this.previous=null}
   if(!this.previous||token!==JSON.stringify([this.previous.hole,this.previous.board]))this.events.push({kind:'CARDS_CONFIRMED',round:this.round,timestamp,hole:[...report.hole],board:[...report.board]});
   this.previous={hole:[...report.hole],board:[...report.board]};
  }
  return {...report,round:this.round,gate:{solver_allowed:!reasons.length,reasons},events_count:this.events.length};
 }
}
