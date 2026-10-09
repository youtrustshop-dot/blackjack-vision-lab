import {useEffect, useRef, useState} from 'react';
import CompactAdvisor from './CompactAdvisor';
import './integration.css';

type Source = {id: string; title: string; url: string; scenario?: string; switch_to?: string};
type Config = {sources: Source[]; cloud_configured: boolean};

async function call(path: string, init?: RequestInit) {
  const response = await fetch('/api/research/r1'+path, {
    ...init, headers: {'x-bjlab-local': '1', ...init?.headers}, cache: 'no-store',
  });
  const value = await response.json();
  if (!response.ok) throw new Error(value.detail || 'Il laboratorio non è disponibile.');
  return value;
}

function useSnapshot(identity: string | null) {
  const [value, setValue] = useState<any>(null);
  const [expires, setExpires] = useState(0);
  const [now, setNow] = useState(performance.now());
  const [error, setError] = useState('');
  useEffect(() => {
    setValue(null); setExpires(0);
    if (!identity) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const started = performance.now();
      try {
        const next = await call('/sessions/'+identity+'/state');
        if (active) {
          setValue(next);
          // Charge the whole polling round trip against original evidence TTL.
          // A new redraw or poll never grants an extra three seconds.
          setExpires(next.stale ? 0 : started+Math.max(0, Math.min(3000, next.evidence_ttl_ms)));
          setError('');
        }
      } catch (e) {
        if (active) {setValue(null); setExpires(0); setError(String(e));}
      } finally {if (active) timer = setTimeout(poll, 150);}
    };
    void poll();
    const tick = setInterval(() => setNow(performance.now()), 75);
    return () => {active = false; clearTimeout(timer); clearInterval(tick);};
  }, [identity]);
  return {value, stale: !value || value.stale || now >= expires, error};
}

export function IntegrationAdvisor() {
  const identity = new URLSearchParams(location.search).get('r1-advisor');
  const {value, stale, error} = useSnapshot(identity);
  return <main className="integration-popup">
    <header><span>Tavolo del laboratorio</span><button aria-label="Chiudi advisor" onClick={() => window.close()}>×</button></header>
    {error && <p role="alert">Sorgente non disponibile</p>}
    <CompactAdvisor report={value?.report} stale={stale} ageMs={value?.evidence_age_ms}/>
    <small>Finestra browser · primo piano non garantito</small>
  </main>;
}

export default function IntegrationLab() {
  const [config, setConfig] = useState<Config | null>(null);
  const [selected, setSelected] = useState('');
  const [identity, setIdentity] = useState<string | null>(null);
  const [cloud, setCloud] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const canvas = useRef<HTMLCanvasElement>(null);
  const currentImage = useRef<HTMLImageElement | null>(null);
  const popup = useRef<Window | null>(null);
  const popupIdentity = useRef<string | null>(null);
  const generation = useRef(0);
  const captureMarks = useRef(new Map<string, number>());
  const displayMarks = useRef(new Set<string>());
  const {value, stale, error: stateError} = useSnapshot(identity);

  useEffect(() => {
    // Explicit laboratory scenario: actual canvas changes only after the real
    // cloud reader is pending. This signal never supplies a turn/card to it.
    const source = config?.sources.find(s => s.id === selected);
    if (value?.counts?.cloud_pending && source?.scenario === 'change_while_pending' && source.switch_to) {
      setSelected(source.switch_to);
    }
  }, [value, config, selected]);

  useEffect(() => {
    if (!identity) return;
    const stopOnExit = () => {
      generation.current++;
      void call('/sessions/'+identity, {method: 'DELETE', keepalive: true}).catch(() => {});
    };
    window.addEventListener('pagehide', stopOnExit);
    return () => {window.removeEventListener('pagehide', stopOnExit); stopOnExit();};
  }, [identity]);

  useEffect(() => {
    let active = true;
    call('/configuration').then(next => {
      if (active) {setConfig(next); setSelected(next.sources[0]?.id || '');}
    }).catch(e => active && setError(String(e)));
    return () => {active = false;};
  }, []);
  useEffect(() => {
    currentImage.current = null;
    const source = config?.sources.find(s => s.id === selected);
    if (!source) return;
    let active = true;
    const image = new Image();
    image.onload = () => {
      if (!active || !canvas.current) return;
      canvas.current.width = image.naturalWidth;
      canvas.current.height = image.naturalHeight;
      canvas.current.getContext('2d')!.drawImage(image, 0, 0);
      currentImage.current = image;
    };
    image.onerror = () => active && setError('Immagine del simulatore non disponibile.');
    image.src = source.url;
    return () => {active = false;};
  }, [selected, config]);

  useEffect(() => {
    if (!identity) return;
    const ownGeneration = ++generation.current;
    let timer: ReturnType<typeof setTimeout>;
    let sequence = 0;
    const capture = async () => {
      const surface = canvas.current;
      if (ownGeneration !== generation.current) return;
      if (!surface || !currentImage.current) {timer = setTimeout(capture, 80); return;}
      const captured = performance.now(), epoch = Date.now();
      try {
        const blob = await new Promise<Blob>((resolve, reject) => surface.toBlob(
          b => b ? resolve(b) : reject(new Error('Cattura non disponibile')), 'image/png'));
        if (ownGeneration !== generation.current) return;
        const ack = await call('/sessions/'+identity+'/capture?sequence='+(sequence++)+'&captured_epoch_ms='+epoch,
          {method: 'POST', body: blob, headers: {'Content-Type': 'image/png'}});
        captureMarks.current.set(ack.capture_ns, captured);
        if (captureMarks.current.size > 128) captureMarks.current.delete(captureMarks.current.keys().next().value!);
      } catch (e) {
        if (ownGeneration === generation.current) setError(String(e));
      } finally {if (ownGeneration === generation.current) timer = setTimeout(capture, 65);}
    };
    void capture();
    return () => {generation.current++; clearTimeout(timer);};
  }, [identity]);

  useEffect(() => {
    if (!identity || stale || !value?.report?.advice) return;
    const stamp = value.evidence_capture_ns;
    if (displayMarks.current.has(stamp)) return;
    const began = captureMarks.current.get(stamp);
    if (typeof began !== 'number') return;
    displayMarks.current.add(stamp);
    // DOM has committed; two RAFs mark a browser rendering opportunity, not
    // a measured physical display scanout or Windows native-window paint.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      void call('/sessions/'+identity+'/display', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
          evidence_capture_ns: stamp, capture_to_dom_ms: performance.now()-began,
          action: value.report.advice.best_action, boundary: 'browser-dom-two-raf',
        })}).catch(e => setError(String(e)));
    }));
  }, [identity, value, stale]);

  const start = async () => {
    setBusy(true); setError('');
    try {
      if (identity) await call('/sessions/'+identity, {method: 'DELETE'});
      const result = await call('/sessions', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({cloud})});
      captureMarks.current.clear(); displayMarks.current.clear(); setIdentity(result.session_id);
    } catch (e) {setError(String(e));} finally {setBusy(false);}
  };
  const stop = async () => {
    generation.current++;
    if (identity) await call('/sessions/'+identity, {method: 'DELETE'}).catch(e => setError(String(e)));
  };
  const analyze = async () => {
    if (!identity) return;
    setBusy(true); setError('');
    try {await call('/sessions/'+identity+'/analyze', {method: 'POST'});}
    catch (e) {setError(String(e));} finally {setBusy(false);}
  };
  const openAdvisor = () => {
    if (!identity) return;
    if (popup.current && !popup.current.closed) {
      if (popupIdentity.current !== identity) popup.current.location.href = '/?r1-advisor='+encodeURIComponent(identity);
      popupIdentity.current = identity;
      popup.current.focus(); return;
    }
    popup.current = window.open('/?r1-advisor='+encodeURIComponent(identity), 'card-lab-r1-advisor', 'popup,width=285,height=240');
    popupIdentity.current = identity;
    if (!popup.current) setError('Il browser ha bloccato la finestra advisor.');
  };

  return <main className="integration-lab">
    <header><small>CARD LAB · CANDIDATO DI RICERCA</small><h1>Dal tavolo al consiglio</h1><p>Pixel del nostro simulatore. Lettura, verifica e advisor sullo stesso stato.</p></header>
    <div className="integration-toolbar">
      <label>Scena<select aria-label="Scena del simulatore" value={selected} onChange={e => setSelected(e.target.value)}>{config?.sources.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
      <label><input type="checkbox" checked={cloud} disabled={!config?.cloud_configured || !!identity} onChange={e => setCloud(e.target.checked)}/>Lotto cloud autorizzato</label>
      <button onClick={() => void start()} disabled={busy || !config}>Avvia sorgente</button>
      <button onClick={() => void analyze()} disabled={busy || !identity}>{busy ? 'Lettura in corso…' : 'Analizza mano'}</button>
      <button onClick={() => void stop()} disabled={!identity}>Interrompi sorgente</button>
      <button onClick={openAdvisor} disabled={!identity}>Apri advisor esterno</button>
      <button onClick={() => popup.current?.close()}>Chiudi advisor</button>
    </div>
    {(error || stateError) && <p role="alert">{error || stateError}</p>}
    <div className="integration-grid"><section><canvas ref={canvas} aria-label="Tavolo acquisito dal browser"/><p>La scala della preview non riduce la risoluzione acquisita.</p></section>
      <section><CompactAdvisor report={value?.report} stale={stale} ageMs={value?.evidence_age_ms}/>
        <p>Acquisizioni: <b data-testid="captures">{value?.counts?.capture_count || 0}</b> · Analisi: <b data-testid="analyses">{value?.counts?.analysis_count || 0}</b></p>
        <p>La finestra esterna è una vista dello stesso motore. Il conteggio della sessione resta non verificato.</p>
        <details><summary>Esamina la prova</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>
      </section></div>
    <p>Questo esperimento verifica il percorso nel browser. Cattura desktop, altri siti e primo piano nativo richiedono prove proprie.</p>
  </main>;
}
