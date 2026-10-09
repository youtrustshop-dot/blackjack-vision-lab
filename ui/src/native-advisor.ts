import {fetchApi} from './api';

export async function nativeControl(operation:'open'|'hide'|'topmost'|'reset'|'minimize',stream_id?:string,table_name?:string,topmost?:boolean){
 const response=await fetchApi('/native/advisor/control',{method:'POST',headers:{'Content-Type':'application/json','X-BJLAB-Local':'1'},body:JSON.stringify({operation,stream_id,table_name,topmost})});
 const value=await response.json();if(!response.ok)throw new Error(value.detail||'Native advisor unavailable.');return value;
}

export async function publishView(stream_id:string,value:unknown){
 await fetchApi('/native/advisor/'+stream_id+'/view',{method:'POST',headers:{'Content-Type':'application/json','X-BJLAB-Local':'1'},body:JSON.stringify(value)});
}
