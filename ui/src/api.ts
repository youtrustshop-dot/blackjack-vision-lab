export type Card = {id:string;rank?:string;suit?:string;face_down?:boolean};
export type Hand = {cards:Card[];bet:number;status:string;from_split:boolean;total:number;soft:boolean;natural:boolean;profit?:number;split_aces?:boolean};
export type Rules = {decks:number;hit_soft17:boolean;blackjack_payout:number;dealer_peek:boolean;enhc:boolean;enhc_loss:string;double_rule:string;double_after_split:boolean;resplit:boolean;max_split_hands:number;resplit_aces:boolean;hit_split_aces:boolean;surrender:string;penetration:number};
export type Snapshot = {advice?:any;session_id:string;seed:number;rules:Rules;phase:string;round_id:number;active_hand:number|null;hands:Hand[];dealer:{cards:Card[];total:number|null;soft:boolean|null};shoe:{id:string;decks:number;total:number;remaining:number;seen:number;counts:number[];running_count:number;true_count:number;penetration:number;unknown_cards:number};insurance:{offered:boolean;taken:boolean;bet:number;profit:number};available_actions:string[];round_profit:number;total_profit:number;bankroll:number;events_count:number;peek_resolved:boolean};
export type Event = {kind?:string;type?:string;index?:number;timestamp?:number;payload?:Record<string,unknown>;[key:string]:unknown};
export const defaultRules:Rules = {decks:6,hit_soft17:false,blackjack_payout:1.5,dealer_peek:true,enhc:false,enhc_loss:'all',double_rule:'any',double_after_split:true,resplit:true,max_split_hands:4,resplit_aces:false,hit_split_aces:false,surrender:'late',penetration:.75};
export const backendConnectionMessage='Il backend locale non risponde. Per questa pagina avvia run.ps1 dalla cartella dei sorgenti, oppure apri l’app desktop.';
export class BackendConnectionError extends Error {
 constructor(){super(backendConnectionMessage);this.name='BackendConnectionError'}
}
export class ApiResponseError extends Error {
 constructor(message:string,public status:number){super(message);this.name='ApiResponseError'}
}
export async function fetchApi(path:string,options?:RequestInit):Promise<Response>{
 try{return await fetch('/api'+path,options)}catch(error){
  if(error instanceof Error&&error.name==='AbortError')throw error;
  if(typeof window!=='undefined')window.dispatchEvent(new Event('bjlab:backend-unavailable'));
  throw new BackendConnectionError();
 }
}
export async function api<T=any>(path:string,data?:unknown):Promise<T>{
 const response=await fetchApi(path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
 if(!response.ok){let msg=await response.text();try{const detail=JSON.parse(msg).detail;msg=typeof detail==='string'?detail:Array.isArray(detail)?detail.map(item=>{const field=item.loc?.filter((x:unknown)=>x!=='body').join(' ')||'Input';return field==='player'&&item.type==='too_short'?'Enter at least two player cards, for example 7 2.':field+': '+(item.msg||'Check this value.');}).join(' '):'The request could not be processed. Check the table settings.'}catch{}throw new ApiResponseError(msg,response.status)}
 try{return await response.json()}catch{throw new ApiResponseError('Risposta del backend non valida. Riprova la connessione.',response.status)}
}
export function download(name:string,data:unknown,type='application/json'){
 const text=typeof data==='string'?data:JSON.stringify(data,null,2);const url=URL.createObjectURL(new Blob([text],{type}));
 const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
