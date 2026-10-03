import {useEffect,useRef,useState} from 'react';
import {Camera,Monitor,Square} from 'lucide-react';
import {captureScreenFrame,ScreenShare,screenSharingError} from './screen-sharing';

export default function ScreenCapture({onCapture}:{onCapture:(file:File)=>void}){
 const owner=useRef<ScreenShare|null>(null);if(!owner.current)owner.current=new ScreenShare();
 const video=useRef<HTMLVideoElement>(null),mounted=useRef(true),operation=useRef(0);
 const [stream,setStream]=useState<MediaStream|null>(null),[pending,setPending]=useState(false),[ready,setReady]=useState(false),[error,setError]=useState(''),[captured,setCaptured]=useState(false);
 const stop=()=>{operation.current++;owner.current?.stop();setStream(null);setReady(false);setPending(false)};
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;operation.current++;owner.current?.stop()}},[]);
 useEffect(()=>{
  if(!stream||!video.current)return;
  const target=video.current;target.srcObject=stream;
  const ended=()=>stop();stream.getVideoTracks().forEach(track=>track.addEventListener('ended',ended));
  void target.play().catch(()=>{if(mounted.current)setError('Anteprima non avviata. Ferma e riprova la condivisione.')});
  return()=>{stream.getVideoTracks().forEach(track=>track.removeEventListener('ended',ended));target.srcObject=null};
 },[stream]);
 const start=async()=>{
  const attempt=++operation.current;setError('');setCaptured(false);setPending(true);
  try{const next=await owner.current!.start();if(mounted.current&&attempt===operation.current&&next){setReady(false);setStream(next)}}
  catch(e){if(mounted.current&&attempt===operation.current)setError(screenSharingError(e))}
  finally{if(mounted.current&&attempt===operation.current)setPending(false)}
 };
 const capture=async()=>{
  const attempt=operation.current;setError('');try{if(!video.current)return;const file=await captureScreenFrame(video.current);if(mounted.current&&attempt===operation.current){onCapture(file);setCaptured(true)}}catch(e){if(mounted.current&&attempt===operation.current)setError(screenSharingError(e))}
 };
 return <section className="screen-capture" aria-label="Condivisione dello schermo">
  <h3><Monitor size={18}/>Osserva una finestra o lo schermo</h3>
  <p>Scegli tu la sorgente nel selettore del browser. L’anteprima resta locale. Acquisisci un fotogramma, seleziona il tavolo nell’immagine e premi «Calibra e importa» per analizzarlo.</p>
  <div className="screen-capture-actions">
   {!stream?<button className="button secondary" onClick={()=>void start()} disabled={pending}><Monitor size={15}/>{pending?'Scegli la sorgente…':'Condividi finestra o schermo'}</button>:<>
    <button className="button primary" onClick={()=>void capture()} disabled={!ready}><Camera size={15}/>Acquisisci fotogramma</button>
    <button className="button secondary" onClick={stop}><Square size={14}/>Ferma condivisione</button>
   </>}
   {pending&&<button className="button secondary" onClick={stop}>Annulla</button>}
   <span role="status">{stream?'Condivisione attiva':pending?'In attesa della tua scelta':'Nessuna sorgente condivisa'}</span>
  </div>
  {stream&&<video ref={video} muted autoPlay playsInline onLoadedData={()=>setReady(true)} aria-label="Anteprima della sorgente condivisa"/>}
  {captured&&<p role="status">Fotogramma pronto nella sezione «Normalizza un’immagine» qui sotto. La cattura non garantisce il riconoscimento di carte con grafica diversa da quella del laboratorio.</p>}
  {error&&<p className="tool-error" role="alert">{error}</p>}
  <p className="screen-browser-note">Usa Chrome o Edge su localhost. Nei browser integrati la condivisione può non essere disponibile; resta possibile caricare uno screenshot. Chiudendo gli strumenti o cambiando sezione la condivisione si ferma.</p>
 </section>;
}
