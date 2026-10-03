export type VisualEvidence={key:string;image:string;report:any;corners?:number[][];output_height?:number};
export function compareClef(result:any,report:any){
 const answers=result?.answers||{},issues:string[]=[];
 const accepted=(key:string)=>answers[key]?.accepted===true?answers[key].value:null;
 const count=Number(accepted('player_count'));
 if(accepted('phase')&&accepted('phase')!==report?.phase)issues.push('The visual models disagree about the game phase.');
 if(accepted('dealer_upcard')&&accepted('dealer_upcard')!==report?.dealer?.[0])issues.push('The visual models disagree about the dealer upcard.');
 if(accepted('player_count')&&count!==report?.player?.length)issues.push('The visual models disagree about the number of player cards.');
 if(answers.readability?.value==='occluded'&&answers.readability?.score>=.90)issues.push('Clef reports an unreadable player card. Confirm the hand.');
 for(let i=1;i<=Math.min(count,4);i++)if(accepted('player_'+i)&&accepted('player_'+i)!==report?.player?.[i-1])issues.push('The visual models disagree about player card '+i+'.');
 const complete=accepted('phase')==='player'&&accepted('readability')==='clear'&&count>=2&&count<=4&&!!accepted('dealer_upcard')&&Array.from({length:count},(_,i)=>accepted('player_'+(i+1))).every(Boolean);
 return {status:issues.length?'disagreement':complete?'agreement':'inconclusive',issues};
}
/** Crop the captured image, rather than a later video frame. */
export async function verificationImage(blob:Blob,report:any){
 const bitmap=await createImageBitmap(blob),bounds=report?.table_bounds;
 const [x,y,w,h]=bounds||[0,0,bitmap.width,bitmap.height];
 const scale=Math.min(1,1024/Math.max(w,h)),canvas=document.createElement('canvas');
 canvas.width=Math.max(1,Math.round(w*scale));canvas.height=Math.max(1,Math.round(h*scale));
 canvas.getContext('2d')!.drawImage(bitmap,x,y,w,h,0,0,canvas.width,canvas.height);bitmap.close();
 return canvas.toDataURL('image/png').split(',')[1];
}
