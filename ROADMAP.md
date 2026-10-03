# Roadmap integrata — Blackjack Vision Lab

Obiettivo: realizzare l'intero laboratorio dei due testi con motore indipendente, solver, simulatore, pipeline visuale, conteggio, replay, dashboard, benchmark, riferimenti ed esperimenti opzionali. Il perimetro resta integro; le fasi ordinano il lavoro e non eliminano requisiti.

Avvio: 3 ottobre 2026. Nessuna durata o prestazione è dichiarata misurata prima della verifica.

## Contratti di correttezza

1. Il solver vede solo carte esposte, regole e storico osservabile. Hole card e ordine futuro sono riservati al valutatore. Peek negativo condiziona le probabilità.
2. Il pool non osservato include carte nascoste e non coincide necessariamente con il solo inventario pescabile. Carte bruciate e osservazioni perse richiedono distribuzioni o gate espliciti.
3. Distinguere EV esatto condizionato, approssimazione e Monte Carlo. Azioni mancanti impediscono di proclamare un ottimo globale.
4. EV normalizzato alla puntata iniziale; settlement coerente per split/double/surrender/insurance/ENHC.
5. Distribuzione, track e classificazione hanno identità separate. Occlusione, spostamento e reveal non duplicano il conteggio.
6. Confronti a pari regole, informazioni, normalizzazione e strategia futura.
7. Score visuale, probabilità calibrata e integrità dello shoe sono separati.
8. Seed, schema eventi, versione, ruleset e dataset rendono gli esperimenti riproducibili.

## Fasi

| ID | Contenuto | Prova richiesta | Stato iniziale |
|---|---|---|---|
| M01 | Rules: deck1/2/4/6/8, S17/H17,payout,peek/AHC/ENHC/OBO,double,DAS,resplit/aces,surrender,penetration | Test regole/settlement e combinazioni invalide | In corso |
| M02 | Engine seeded:shoe,soft/hard,natural,bust,dealer,azioni,insurance | Conservazione carte e replay seed | In corso |
| M03 | Solver finite-shoe,DP,memoization,basic generata,composizione,peek/hidden probabilities | Enumerazione indipendente piccoli shoe e golden | In corso |
| M04 | Split/resplit con stato congiunto e puntate, precision budget | Golden split/DAS/aces/OBO e nessun falso-esatto | In corso |
| M05 | Hi-Lo RC/TC/rounding/history,I18/Fab4,KO,HiOpt1/2,OmegaII,Zen/custom | Tags,invarianti,deviazioni | In corso |
| M06 | Shoe observed/unknown/removed,shuffle/ID,penetration,KNOWN/INFERRED decks | Replay inventario,missing gate,posterior | In corso |
| M07 | Event sourcing,correzioni,replay frame/event,timeline,CSV/JSON versionati | Stato identico e log verificato | In corso |
| M08 | Simulatore visuale:seed,temi,design,resize,animazione,speed,overlap,blur,scaling | Groundtruth separata e render parametrizzati | In corso |
| M09 | Capture:native,screenshot,video,window;ROI/prospettiva | Adapter fixtures,frame/timestamps,geometria | In corso |
| M10 | Detection rank/suit/zone/buttons/OCR/shuffle;template/OpenCV/classifier/ONNX | Benchmark su temi/sessioni separati | In corso |
| M11 | Tracker conferma Nframes,identity,occlusion/movement/split/reveal | Duplicati/missed/count drift per sessione | In corso |
| M12 | Confidence vision/state/shoe/decks,calibration,robustness gate | Error bins,session integrity,EV regret,withheld | In corso |
| M13 | Dashboard:table,EV,3strategies,shoe/composition,FPS/latency/drops,replay | Browser flows e visual QA | In corso |
| M14 | MonteCarlo scientifico:policies,EV/errors/regret/latency,CI,CSV/JSON | Seeded runs,statistical intervals,no leakage | In corso |
| M15 | Golden,unit/property/integration/regression,differential failures | CI e provenance | Pianificato |
| M16 | hhoppe,FreeBJ,mhluska,MGP,BJStrategySimulator,CardSharp | Commit/licenza/capability/confronti eseguiti | Pianificato |
| M17 | Roboflow,martinabeleda,template/OpenCV/custom/ONNX,discardtray | Licenze,session split,MAE/RMSE/calibration | Pianificato |
| M18 | Jev/Laya phase/anomaly/uncertainty vs state machine;RLCard opzionale | Accuracy/latency/calibration/failure cases reali | Pianificato |
| M19 | React+TS+Tauri desktop e packaging headless | Desktop build e launch/install smoke | Pianificato |
| M20 | Performance target30FPS,feedback<100ms dove praticabile e audit | Hardware,p50/p95,pacchetto e tutti i requisiti | Pianificato |

## Ordine operativo

M01–M07 con validazione presente dall'inizio. M08–M12 sfruttano lo stesso log e sessioni etichettate. M13–M15 rendono il laboratorio utilizzabile e verificabile. M16–M18 estendono prove indipendenti ed esperimenti. M19–M20 completano distribuzione e audit. Solver ricalcolato per stato, non per frame; calcoli lunghi non bloccano il tavolo.

## Esperimenti

- Basic vs Hi-Lo vs composizione a pari regole/informazione.
- Native state vs vision per il costo della percezione.
- Ablation tracking/temporal confirmation/gate.
- Score calibrato vs non calibrato; EV regret oltre action accuracy.
- Detector concorrenti su stessi dataset/hardware.
- KNOWN vs INFERRED decks.
- Split esatto vs approssimazione dichiarata vs MonteCarlo.
- State machine vs Jev/Laya su fasi/anomalie.
- Discardtray MAE/RMSE e generalizzazione tra sessioni.

## Accettazione finale

Ogni requisito in docs/REQUIREMENTS.json richiede una prova ispezionata. File vuoti, adapter non esercitati, screenshot statici e test di sola esistenza non provano completamento. I contratti obbligatori si chiudono con test, esecuzioni e audit; un risultato negativo documentato conclude un esperimento, senza promuovere il modello all'uso operativo. Le condizioni già presenti nei testi — confronto dove supportato, modelli quando praticabile e RLCard futuro — restano esplicite. Laya è stato rinviato dall'utente («poi mettiamo laya»). Nessuna opzione non eseguita è trasformata in un benchmark positivo.

## Evidenze della consegna corrente

Le righe della tabella precedente conservano lo stato iniziale della pianificazione. Lo stato aggiornato è in `docs/REQUIREMENTS.json`, le misure in `docs/STATUS.md` e i report originali in `validation/`, `experiments/` e `release/`.

- M01–M07: rules/engine/solver indipendenti, strategie generate con modello esplicito, split congiunto entro budget, sistemi di conteggio, inventario e posteriori mazzi. Correzioni immutable e replay sia eventi sia frame JPEG con prefisso verificato.
- M08–M13: temi e design classico/essenziale, velocità di animazione, PNG/video/capture locale, quattro angoli, recognition/OCR controllato, tracker e gate. Dashboard con bounding box, EV, tre strategie, shoe e metriche misurate; FPS/drop live restano null quando non osservati.
- M14–M15: run policies fino al budget, intervalli per batch, ablation1/3frame, costo nativo/pixel, RC/TC e regret con astensioni null. Golden analitici versionati, proprietà su384 mani e corpus differential2.000 stati; discrepanze originali e risoluzioni separati.
- M16: hhoppe, FreeBJ, mhluska e BJSS eseguiti con pin e modelli equivalenti dove possibile; CardSharp studiato per architettura, MGP per manuale/codice/licenza. MGP legacy non espone CLI supportata, quindi nessun output numerico viene attribuito al programma.
- M17: dataset sintetico e fotografie MIT, confronto reale Martin e tray con fallimenti/astensioni conservati. Roboflow resta unavailable; ONNX ha un adapter esplicito, senza pesi addestrati inventati.
- M18: baseline state machine realmente valutata; adapter Laya/Jev con contract test. Laya successivo per decisione dell'utente; RLCard conservato come ricerca futura.
- M19–M20: eseguibile/installer Windows, backend standalone, licenze e manifest; prove di avvio, chiusura, installazione e rimozione nel workspace. Target di prestazione valutati sul computer reale e sul contratto controllato, senza garanzia30FPS/<100ms per ogni operazione.

L'accettazione di release richiede le prove definitive di distribuzione e l'archivio integro. I limiti di percezione fotografica e di budget non vengono nascosti dalla chiusura della consegna corrente.
