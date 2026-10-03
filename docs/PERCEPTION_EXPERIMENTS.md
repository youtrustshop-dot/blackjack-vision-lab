# M14: conteggio osservabile, costo e conferma temporale

Il run reale del 3 ottobre 2026 ha elaborato le 360 immagini del test sintetico, in 60
gruppi sessione/tema, in 8,58 secondi. Il manifest ha SHA-256
`7fe3b5d7f624bac4c71a1c3c2aea1f7c90daf063c4bff4ef838e110908de481e`.
Le sessioni di test sono disgiunte dalla calibrazione; burgundy è il tema tenuto fuori
dagli altri split. Non sono state modificate immagini, soglie o associazioni dopo il test.

Gli artefatti eseguiti sono in `validation/results/perception-ablation/`:

- `summary.json`: aggregati, budget, ambiente e hash del codice.
- `raw-results.json`: 720 snapshot, input osservabile, stato ricostruito, gate e journal
  finali per ciascuna modalità.
- `regret-samples.json`: input e output effettivi dei solver, incluse le astensioni.
- `pixel-source-digests.json`: hash delle 360 immagini realmente lette.

## Protocollo

Il valutatore aggiorna il proprio inventario dalle etichette osservabili: un retro ha
rank e seme null; una carta precedentemente vista conserva la sua identità durante
un'occlusione. Il detector riceve soltanto pixel RGB. Due tracker indipendenti ricevono
le medesime detection, uno con `stable_frames=1`, l'altro con `stable_frames=3`, entrambi
con soglia fissa 0,90. Il numero di mazzi del fixture è dichiarato D=1 e il confine della
singola mano è pubblico. Gli ID delle etichette servono soltanto al matching geometrico
nel valutatore, con IoU ≥0,5; non raggiungono i tracker.

RC usa Hi-Lo sui soli rank conosciuti. TC divide RC per `(52D - carte fisiche osservate)/52`;
anche una carta coperta riduce il numero fisico restante, senza sottrarre un rank dal pool
informativo. La deriva L1 somma le differenze assolute sulle 13 molteplicità dei rank.
`state_exact` in questo report significa inventario di conteggio esatto: molteplicità
dei rank, numero fisico osservato e numero di rank sconosciuti coincidono. Non certifica
da solo identità, semi, zone o completezza di ciò che non è stato rilevato. Eventi mancanti,
duplicati e non associati sono misurati separatamente sui journal finali. La verifica dei
semi e delle etichette temporali completa rimane nel benchmark `validation/results/vision/`.

Il gate è quello effettivo del tracker. Un'opportunità di analisi nel fixture richiede
un rank dealer visibile e almeno due rank player, con totale inferiore a 21. È una
condizione osservabile fissata per l'esperimento, non una fase reale certificata: il
dataset non contiene una partita completa né un ordine di distribuzione legale garantito.
Le analisi EV usano le regole esplicite salvate nel report; queste regole non vengono
inferite dalle etichette delle immagini.

## Risultati conservati

| Misura | Conferma 1 frame | Conferma 3 frame |
|---|---:|---:|
| Frame con RC esatto | 360/360 (100%) | 158/360 (43,89%) |
| RC MAE / massimo errore assoluto | 0 / 0 | 0,7778 / 4 |
| TC MAE / RMSE | 0 / 0 | 0,8648 / 1,3039 |
| Deriva L1 media dei rank | 0 | 2,0694 |
| Inventario di conteggio esatto per frame | 360/360 | 59/360 |
| Inventario finale esatto per gruppo | 60/60 | 59/60 |
| Eventi finali mancanti / duplicati / non associati | 0 / 0 / 0 | 0 / 0 / 0 |
| Gate di integrità aperto | 299/360 | 59/360 |
| Gate aperto con inventario di conteggio inesatto | 0 | 0 |
| Analisi ammesse / opportunità del fixture | 48/72 | 0/72 |
| Analisi ammesse con inventario inesatto | 0 | 0 |
| Pixel pipeline p50 / p95, ms | 21,804 / 26,826 | 21,679 / 26,593 |

Non ci sono eventi di distribuzione persi, ma nella modalità a tre frame un rank rivelato
non è ancora confermato nell'ultimo frame di un gruppo: la carta fisica è presente e il
gate resta provvisorio. Il risultato 59/60 e i ritardi intermedi rimangono nel report.
La frazione di RC esatto può superare quella dell'inventario esatto perché rank diversi
possono avere lo stesso contributo Hi-Lo. Il dataset cambia visibilità e valore entro
sequenze di soli sei frame: questa misura espone il costo di attendere tre conferme.
Non costituisce una raccomandazione di ridurre la soglia in immagini esterne rumorose.

## Costo misurato e regret

Il bookkeeping dello stato nativo osservabile misura p50 0,03365 ms e p95 0,05333 ms.
Il costo visivo misura apertura e conversione RGB, detection, aggiornamento tracker e
replay effettivamente eseguiti. Il decode p95 è 16,754 ms e la detection p95 10,179 ms;
i percentili delle parti non si sommano per ottenere il percentile della pipeline.
La detection comune è misurata una sola volta per immagine e conteggiata nel costo di
entrambe le modalità. Non sono inclusi attesa di cattura, rete o rendering del simulatore;
queste latenze non sono una misura di FPS live o della frequenza configurata nell'UI.

Per contenere il costo, il driver seleziona i primi quattro stati osservabili distinti
eleggibili, nel normale ordine di lettura, e chiama realmente il solver nativo. Se il gate
visivo consente l'analisi, chiama anche un solver indipendente sul pool e sul contesto
visivi. Budget per chiamata: 250 ms e 15.000 nodi. Il regret è
`max(EV_native) - EV_native[azione_visiva]`, in profitto netto per puntata originale,
e viene calcolato soltanto quando entrambe le analisi sono complete e l'azione è legale.

Con conferma a un frame, quattro confronti sono completi: quattro azioni coincidenti,
regret medio 0. Con conferma a tre frame, tutti e quattro sono trattenuti dal gate:
regret e frazione di accordo sono null. Quattro stati sono una verifica del percorso,
non una stima rappresentativa delle prestazioni strategiche. I frame della stessa
sessione sono correlati; le frazioni sono descrittive e non hanno intervalli binomiali
costruiti assumendo osservazioni indipendenti.

## Riproduzione

Da root del prodotto, con le dipendenze Python installate:

```text
python validation/tools/perception_ablation.py datasets/synthetic_cards --output validation/results/perception-ablation --regret-samples 4 --solver-ms 250 --solver-nodes 15000
python -m pytest tests/test_perception_experiments.py -q
```

Il microtest eseguito ha dato 3 passed in 1,00 s: inventario coperto separato dal rank,
pixel effettivi con occlusione e reveal, ritardo di conferma, gate e replay dei quattro
ID. Un test rifiuta configurazioni non valide prima di leggere immagini. Le latenze
variano con macchina e carico; gli hash permettono di verificare dati e codice del run.
