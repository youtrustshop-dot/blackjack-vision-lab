/** Parse user-entered cards before sending any request. Suit symbols are optional. */
export function parseCardInput(value:string,field:string,min=0,max=416):string[]{
 const tokens=value.trim()?value.toUpperCase().trim().split(/[\s,;·+|]+/):[];
 if(tokens.length<min)throw new Error(field==='Player cards'?'Enter at least two player cards, for example 7 2.':'Enter one dealer upcard, for example 6.');
 if(tokens.length>max)throw new Error(field==='Dealer upcard'?'Enter exactly one dealer upcard.':`${field}: too many cards.`);
 return tokens.map(token=>{
  const plain=token.replace(/[♠♣♥♦]/g,'');
  const alias=plain==='ACE'||plain==='ASSO'||plain==='1'?'A':plain;
  const match=alias.match(/^(10|[A2-9TJQK])(?:[SHDC])?$/);
  if(!match)throw new Error(`${field}: unrecognized card “${token}”. Use A, 2–10, J, Q or K separated by spaces.`);
  return match[1]==='T'?'10':match[1];
 });
}
