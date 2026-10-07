export type Correction = {frame:number;original:unknown;corrected:unknown;note:string;createdAt:number};
export function readCorrections(value:string|null):Correction[]{
 if(!value)return [];
 if(value.length>5_000_000)throw new Error('Correction history exceeds the local limit; original storage retained');
 const entries=JSON.parse(value);
 if(!Array.isArray(entries)||entries.length>500||entries.some(c=>!c||!Number.isInteger(c.frame)||c.frame<0||c.frame>=2000||!c.corrected||typeof c.corrected!=='object'||Array.isArray(c.corrected)||typeof c.note!=='string'||c.note.length>2000||!Number.isFinite(c.createdAt)))throw new Error('Invalid correction history; original storage retained');
 return entries;
}
export function parseCorrection(text:string):unknown {
 if(text.length>30_000)throw new Error('Correction exceeds 30 KB');
 const value=JSON.parse(text);
 if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Use a JSON object for the corrected observation');
 return value;
}
export function differences(original:unknown,corrected:unknown):{field:string;before:unknown;after:unknown}[]{
 const before=(original&&typeof original==='object'?original:{}) as Record<string,unknown>;
 const after=(corrected&&typeof corrected==='object'?corrected:{}) as Record<string,unknown>;
 return [...new Set([...Object.keys(before),...Object.keys(after)])].sort().filter(key=>JSON.stringify(before[key])!==JSON.stringify(after[key])).map(field=>({field,before:before[field]??null,after:after[field]??null}));
}
