# Stato verificato — 3 ottobre 2026

La consegna corrente implementa il laboratorio controllato dei due testi: motore, solver, conteggio, percezione, shoe, replay, dashboard, esperimenti e verifiche indipendenti. Laya resta rinviato dall’utente. Installer e pacchetto sorgente verificati.

## Prove eseguite

- **246 test e 10 subtest passati**, report `TEST_RESULTS.xml`; proprietà su 32 configurazioni ×12 mani. Warning Starlette/httpx conservato.
- TypeScript/Vite riusciti; Chrome isolato: **7 flussi principali +5 avanzati**, incluse carte coperte, EV, mobile, correzioni/calibrazione, posteriori, design/velocità e replay di JPEG video senza futuro nel prefisso.
- **2.000 stati** finite-shoe, cinque deck count ×S17/H17: tutte le azioni ottimali concordano. 279 EV fuori tolleranza nel riferimento approssimato effort3 sono conservati; tutti tornano entro1e-7 a effort4, massimo errore diagnostico1,82e-10. Nessun input o tolleranza modificati. Gli originali restano `failed`; la risoluzione è un artifact separato.
- Tre bug reali trovati nell’audit e corretti: puntate prima del peek, double sulle mani split già a21 e fase di peek inferita dopo hit/split con early surrender. Golden analitici e regressioni indipendenti accompagnano le correzioni.
- BJSS:6 stati/24EV concordanti entro1e-9, AGPL isolato. FreeBJ e mhluska:120.000 round per motore nei confronti always-stand; intervalli includono zero. FreeBJ condizionato fallito e dichiarato non equivalente.
- Backend standalone, vera finestra Tauri e chiusura regolare verificati; installer definitivo e cattura del client attestati nei report della cartella `release`.

## Percezione e risultati negativi

Generati1.560 PNG da120 sessioni; calibrazione/test separati. Su360 frame test:1.632 detections geometriche corrette,1.452 rank/semi e180 dorsi corretti, zero FP/FN. Detection p95 14,68ms; tracking finale59/60 esatto, una rivelazione provvisoria conservata. Pipeline p95 32,81ms. Calibrazione per detection: Brier0,0000103, ECE0,000908; non probabilità d’integrità dell’intera sessione.

Ablation reale360 frame/60 gruppi: conferma1frame RC100%, TC MAE0; conferma3frame RC43,89%, TC MAE0,8648 perframe, con ritardo e finale59/60. Nessuno stato di conteggio/inventario inesatto ammesso dal gate nel benchmark; questa metrica non certifica semi, identità o zone. Quattro confronti EV completi: regret0; quattro astensioni: regret null. Pipeline p95 circa26,8ms, bookkeeping nativo0,053ms. Denominatori/limiti in `PERCEPTION_EXPERIMENTS.md`.

Deck inference heldout47,92%; tray sintetico MAE0,315 carte ma spessore nuovo MAE13,87 e copertura0%. Foto vere: primo tray predictor fallisce, versione prudente si astiene su9/9 test e7/7 overflow. Martin: nostra baseline0/13, reference13/13 su una sua fixture; nessuna generalizzazione fotografica rivendicata.

## Ambito e opzioni conservate

La visione supporta l’artwork controllato e clip di un solo round; non segmenta automaticamente video arbitrari. Import indipendenti non ereditano mazzi dalla sessione. I posteriori non diventano un numero certo; unknown inventory blocca il solver. FPS live/drop restano null quando non misurati, distinti dal throughput offline.

Basic strategy generata nel modello replacement; celle finite composition-dependent separate. Split esatto entro budget, analisi incomplete senza falso best globale. Le misure non sono garanzie30FPS/<100ms su ogni stato; OCR e decisioni complesse hanno costi separati. Hardware in `HARDWARE.json`.

Laya/Jev sono adattatori opzionali con test, modelli reali non eseguiti e Laya rinviato. RLCard resta ricerca futura; ONNX/Roboflow non hanno pesi locali validati. MGP: manuale/licenza/capability studiati, runtime legacy senza CLI, nessun numero inventato. Roadmap e `REQUIREMENTS.json` conservano questi stati.
