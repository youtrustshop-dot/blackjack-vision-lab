import {useState} from 'react';
import FrameReplay from './FrameReplay';
export function OfflineReplay(){
 const [result,setResult]=useState<any>(null),[error,setError]=useState(''),[text,setText]=useState('');
 const loadText=(content:string)=>{try{if(new TextEncoder().encode(content).length>15_000_000)throw new Error('Report exceeds 15 MB');const value=JSON.parse(content);if(!Array.isArray(value.frames)||!value.frames.length||value.frames.length>2000)throw new Error('Use a report containing 1–2000 sampled frames');setResult(value);setError('')}catch(e){setError(String(e))}};
 const load=async(file:File)=>{try{if(file.size>15_000_000)throw new Error('Report exceeds 15 MB');loadText(await file.text())}catch(e){setError(String(e))}};
 return <section className="panel"><h2>Offline frame report</h2><p>Choose an existing Vision Lab JSON report. This inspector reads it locally without contacting the server.</p><label>Choose offline frame report<input type="file" accept="application/json,.json" onChange={e=>{const file=e.target.files?.[0];if(file)void load(file)}}/></label><details><summary>Paste an offline JSON report</summary><label>Report JSON<textarea rows={4} maxLength={15000000} value={text} onChange={e=>setText(e.target.value)}/></label><button className="button secondary" disabled={!text.trim()} onClick={()=>loadText(text)}>Open pasted report</button></details>{error&&<p role="alert">{error}</p>}{result&&<FrameReplay result={result}/>}</section>;
}
