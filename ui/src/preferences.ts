import {defaultRules,Rules} from './api';

export type GameMode='standard'|'simple'|'custom';
export const rulesForMode=(mode:GameMode,existing:Rules=defaultRules):Rules=>mode==='simple'?{...existing,double_rule:'none',double_after_split:false,resplit:false,max_split_hands:1,surrender:'none'}:mode==='standard'?{...defaultRules,decks:existing.decks,hit_soft17:existing.hit_soft17}:existing;
export function readRules():Rules{try{const saved=JSON.parse(localStorage.getItem('bjlab.rules.v1')||'null');if(saved&&[1,2,4,6,8].includes(saved.decks))return {...defaultRules,...saved}}catch{}return {...defaultRules}}
export function saveRules(rules:Rules){try{localStorage.setItem('bjlab.rules.v1',JSON.stringify(rules))}catch{}}
export function isFirstVisit(){try{return !localStorage.getItem('bjlab.rules.v1')&&!localStorage.getItem('bjlab.language')}catch{return false}}
export function handValue(cards:string[]){const ranks=cards.map(c=>c==='A'?1:['10','T','J','Q','K'].includes(c)?10:Number(c));const hard=ranks.reduce((a,b)=>a+b,0);const soft=ranks.includes(1)&&hard+10<=21;return {total:hard+(soft?10:0),hard_total:hard,soft,ace_values:ranks.filter(x=>x===1).map((_,i)=>soft&&i===0?11:1),alternative_total:soft?hard:null}}


export {SharedDisplay} from './shared-display';
