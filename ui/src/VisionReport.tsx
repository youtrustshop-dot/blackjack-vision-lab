import {Activity,Clock,ScanLine} from 'lucide-react';
import './vision-report.css';
import DeckEstimate from './DeckEstimate';
import FrameReplay from './FrameReplay';

const metric=(value:unknown,unit='ms')=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(1)+' '+unit:'Non misurato';
const symbols:Record<string,string>={S:'♠',H:'♥',D:'♦',C:'♣'};

export function DetectionOverlay({detections}:{detections:any[]}){
 return <svg className="detection-overlay" viewBox="0 0 960 600" aria-label="Bounding box delle carte riconosciute">
  {detections.map((d,index)=>{const [x,y,w,h]=d.bbox||[];if(![x,y,w,h].every(Number.isFinite))return null;
   const label=d.face_down?'Coperta':String(d.rank||'?')+(symbols[d.suit]||d.suit||'');
   return <g key={index}><rect x={x} y={y} width={w} height={h}/><text x={x+3} y={Math.max(15,y-5)}>{label}</text></g>})}
 </svg>;
}

export default function VisionReport({result}:{result:any}){
 if(!result)return null;
 const video=result.frame_source==='local-video';
 const gate=result.summary?.gate||result.state?.gate;
 return <><DeckEstimate estimate={result.deck_estimation} aggregate={video}/><FrameReplay result={result}/><section className="panel vision-metrics" aria-label="Metriche della percezione">
  <div className="panel-header"><h2><Activity size={16}/>Misure della pipeline</h2><small>{video?'Video locale':result.frame_source==='uploaded-image'?'Immagine importata':'Frame del simulatore'}</small></div>
  <div className="vision-metric-grid">
   <div><Clock size={15}/><span>Latenza pixel {video?'media':'completa'}</span><strong>{metric(video?result.mean_frame_ms:result.full_pixel_latency_ms)}</strong></div>
   <div><ScanLine size={15}/><span>Detection</span><strong>{metric(result.detection_ms)}</strong></div>
   <div><span>Tracking</span><strong>{metric(result.tracking_ms)}</strong></div>
   <div><span>OCR metadati</span><strong>{metric(result.metadata_ms)}</strong></div>
   <div><span>Throughput {video?'video':'pixel'}</span><strong>{metric(video?result.pipeline_fps:result.full_pixel_fps,'frame/s')}</strong></div>
   <div><span>Frame distinti analizzati</span><strong>{result.processed_frames??'—'}</strong></div>
   <div><span>FPS dello stream</span><strong>{metric(result.stream_fps,'FPS')}</strong></div>
   <div><span>Frame persi</span><strong>{typeof result.drop_count==='number'?result.drop_count:'Non misurati'}</strong></div>
   {video&&<><div><span>Latenza frame p95</span><strong>{metric(result.p95_frame_ms)}</strong></div><div><span>Frame decodificati</span><strong>{result.decoded_frames??'—'}</strong></div></>}
  </div>
  <p className="panel-caption">{video?'Il throughput include decodifica ed elaborazione dei frame campionati.':'Una singola immagine viene confermata con '+(result.tracker_updates??'—')+' aggiornamenti del tracker. Il throughput è una misura di elaborazione, non una frequenza di acquisizione live.'}{video&&typeof result.sampled_out_frames==='number'&&' '+result.sampled_out_frames+' frame saltati per campionamento.'}{gate&&' Gate: '+gate.status+'.'}</p>
 </section></>;
}
