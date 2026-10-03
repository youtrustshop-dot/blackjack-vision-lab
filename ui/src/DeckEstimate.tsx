import {localize} from './localize';
export default function DeckEstimate({estimate,aggregate=false}:{estimate:any;aggregate?:boolean}){
 if(!estimate)return null;
 const known=estimate.mode==='KNOWN';
 const sources:Record<string,string>={'configured-session':'Sessione configurata','explicit-upload-parameter':'Dichiarazione per l’immagine','explicit-video-parameter':'Dichiarazione per il video','inferred-confirmed-cards':'Carte confermate dal tracker'};
 return localize(<section className="panel deck-estimate" aria-label="Stima del numero di mazzi">
  <div className="panel-header"><h2>Numero di mazzi{aggregate?' · esito del clip':''}</h2><span className="badge">{known?'KNOWN · DICHIARATO':'INFERRED · INCERTO'}</span></div>
  <div className="deck-estimate-body"><div><strong>{known?estimate.decks+' mazzi':'Numero non determinato'}</strong><p>{sources[estimate.source]||estimate.source}</p></div>
   {!known&&<div className="deck-posterior">{Object.entries(estimate.posterior||{}).map(([decks,p])=><div key={decks}><span>{decks} mazzi</span><div><i style={{width:(typeof p==='number'?p*100:0)+'%'}}/></div><b>{typeof p==='number'?(p*100).toFixed(1)+'%':'—'}</b></div>)}</div>}
   <p className="panel-caption">{known?'Il valore proviene dalla configurazione dichiarata.':'La distribuzione deriva dalle carte confermate; il massimo del posteriore non rende noto il numero di mazzi. Il solver resta bloccato finché manca un inventario affidabile.'} Osservazioni: {estimate.observations??0}. {estimate.status==='inconsistent'?'Evidenza incompatibile con i candidati: revisione necessaria.':''}</p>
   <details><summary>Assunzioni della stima</summary><p>{estimate.assumptions}</p><p>{estimate.certainty_semantics}</p></details>
  </div>
 </section>);
}
