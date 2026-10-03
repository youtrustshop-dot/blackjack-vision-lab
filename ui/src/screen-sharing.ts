/** Own only a display stream explicitly selected by the user. */
export class ScreenShare {
 private stream:MediaStream|null=null;
 private generation=0;
 constructor(private acquire:()=>Promise<MediaStream>=()=>{
  if(!navigator.mediaDevices?.getDisplayMedia)throw new Error('Questo browser non supporta la condivisione. Apri questa pagina in Chrome o Edge, oppure carica uno screenshot.');
  return navigator.mediaDevices.getDisplayMedia({video:{frameRate:{ideal:15,max:30}},audio:false});
 }){}
 async start():Promise<MediaStream|null>{
  this.stop();const attempt=this.generation;
  const stream=await this.acquire();
  if(attempt!==this.generation){stream.getTracks().forEach(track=>track.stop());return null}
  this.stream=stream;return stream;
 }
 stop(){this.generation++;const stream=this.stream;this.stream=null;stream?.getTracks().forEach(track=>track.stop())}
}

export function screenSharingError(error:unknown):string{
 if(error instanceof Error){
  if(['NotAllowedError','AbortError'].includes(error.name))return 'Condivisione annullata o non autorizzata. Puoi riprovare e scegliere la finestra.';
  if(error.name==='NotReadableError')return 'La sorgente non è acquisibile. Scegli un’altra finestra o carica uno screenshot.';
  return error.message;
 }
 return 'Impossibile avviare la condivisione.';
}

export async function captureScreenFrame(video:HTMLVideoElement):Promise<File>{
 if(video.readyState<2||!video.videoWidth||!video.videoHeight)throw new Error('Attendi che l’anteprima sia pronta.');
 const canvas=document.createElement('canvas');
 const scale=Math.min(1,1920/Math.max(video.videoWidth,video.videoHeight));
 canvas.width=Math.max(1,Math.round(video.videoWidth*scale));canvas.height=Math.max(1,Math.round(video.videoHeight*scale));
 const context=canvas.getContext('2d');if(!context)throw new Error('Acquisizione del fotogramma non disponibile.');
 context.drawImage(video,0,0,canvas.width,canvas.height);
 const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('Acquisizione del fotogramma non riuscita.')),'image/png'));
 return new File([blob],'schermo-'+Date.now()+'.png',{type:'image/png'});
}
