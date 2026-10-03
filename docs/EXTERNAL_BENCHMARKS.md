# Fotografie reali e confronti esterni

Questi esperimenti sono separati dal core e dalla simulazione controllata. I report contengono
risultati realmente eseguiti, inclusi fallimenti e astensioni. Un comando completato non significa
che il modello abbia superato una validazione per l'uso operativo.

## Discard tray: acquisizione e split cronologico

La fonte è [mhluska/blackjack-discard-tray-photos](https://github.com/mhluska/blackjack-discard-tray-photos),
commit `3d7ab1bfd0b7ea0235bea085488427fcf7520e69`, con
[licenza MIT](https://github.com/mhluska/blackjack-discard-tray-photos/blob/3d7ab1bfd0b7ea0235bea085488427fcf7520e69/LICENSE).
La licenza è stata verificata prima dell'acquisizione dei pixel. Il README descrive una singola sequenza:
foto del vassoio vuoto e una foto dopo ogni carta, fino a 364 carte; 312 carte sono la capacità nominale
del vassoio da sei mazzi. Il conteggio dell'evaluator è il numero del file meno uno.

Sono state acquisite 41 immagini originali da 4032×3024 pixel, 379.241.637 byte, e verificate sia con
SHA-256 sia contro il Git blob del commit. Foto e codice esterno restano in `work/`, fuori dal bundle
di produzione. `source-manifest.json` conserva conteggi, split, hash e provenienza; `SOURCE_LICENSE.txt`
conserva il testo della licenza. Non è stato eseguito alcuno script della repository esterna.

| Split | Foto | Conteggi |
|---|---:|---|
| Train | 17 | subset 0–208 |
| Calibrazione | 8 | 216–272, passo 8 |
| Test capacità normale | 9 | 280–312, passo 4 |
| Overflow | 7 | 320–364 |

La ROI e le soglie sono state scelte guardando soltanto vuoto, 52 e 156 carte del train, poi salvate
nel protocollo prima della prima misura sul test. Il predictor riceve pixel RGB e una calibrazione
congelata: i conteggi del filename entrano solo nel fit e nell'evaluator. Misura il bordo anteriore
della pila tramite il dorso blu e la base nera, poi stima le carte con regressione lineare. È un
esperimento specifico della telecamera e del dorso, non un riconoscitore universale del vassoio.

## Fallimento conservato e gate di astensione

Il primo run ha erroneamente trattato assenza del dorso blu come pila vuota. Nelle foto successive
i dorsi rossi non soddisfano quella misura: il run iniziale ha MAE **296 carte** nel test normale
e **343,43 carte** nell'overflow, con copertura della banda empirica **0%** in entrambi.
`initial-unsafe-zero-report.json`, `initial-model.json`, `initial-protocol.json` e
`initial-runner-source.txt` conservano il risultato. L'hash dell'archivio del codice è stato verificato
uguale al `runner_sha256` del report originale.

È stato corretto soltanto il gate: un segnale assente richiede revisione e restituisce stima null.
ROI, pixel threshold e regressione non sono stati adattati sul test visto. Le righe di calibrazione
senza misura sono escluse dalla banda e contate separatamente (4 su 8 misurabili). Il report prudente
successivo conserva **9/9 astensioni sul test** e **7/7 sull'overflow**; MAE e copertura sono null
perché non esistono stime numeriche valide. `deployment_ready` resta false. La latenza p95 della
misura, inclusa decodifica e resize, è circa 366 ms sul test e 360 ms sull'overflow in questo host.

Non si è prodotta una validazione positiva sul mondo reale. Anche una misura riuscita su questa
sequenza non dimostrerebbe generalizzazione a sessioni indipendenti, nuovi mazzi o nuove telecamere.
Una futura revisione del detector deve essere validata con immagini nuove, dopo aver congelato
nuovi parametri. Le bande sono residui empirici; non probabilità di correttezza dello stato.

## Confronto Martin su una fixture reale

La fonte è [martinabeleda/blackjack-tracker](https://github.com/martinabeleda/blackjack-tracker),
commit `5145a1260a7a7750f8a5fd56d60702ea8e66c30d`,
[MIT](https://github.com/martinabeleda/blackjack-tracker/blob/5145a1260a7a7750f8a5fd56d60702ea8e66c30d/LICENSE).
Sono stati verificati e acquisiti il modulo `cards.py`, 13 template di rango e le fixture disponibili.
Il confronto effettivo usa **solo club1**, con 13 carte: i ranghi provengono dall'ordine del README,
i box sono annotazioni manuali salvate prima dell'inferenza e verificate visivamente.
I duplicati 1/2 e 3/4 descritti dalla fonte non sono stati contati come immagini indipendenti.

Entrambi i detector ricevono la stessa immagine canonica ottenuta dalla homography di quattro
angoli manuali del tappeto; le detection sono rimappate nell'immagine originale. L'evaluator usa
IoU≥0,5 e conserva falsi positivi, carte mancate e ranghi errati.

| Detector | Carte trovate | Ranghi corretti su tutte le carte | Latenza del singolo run |
|---|---:|---:|---:|
| Baseline template del renderer BJLab | 0/13 | 0/13 | 5,62 ms |
| Martin OpenCV originale | 13/13 | 13/13 | 29,62 ms |

L'originale Martin riconosce il rango e non il seme: suit accuracy è null. I suoi score sono
differenze di pixel non normalizzate, non confidence calibrate. Il confronto usa un caricamento
isolato e revisionato del codice da `work/`: solo compatibilità `findContours` OpenCV3→4 e rotazione
esatta di 90° al posto della dipendenza `imutils`. Parametri e soglia di matching originali non sono
stati modificati. GUI e script di avvio non vengono eseguiti. Il codice esterno non entra nel core.

È una **fixture dello stesso progetto dei template**, con possibile condivisione di carte e condizioni
fotografiche. Le 13/13 corrette non sono una misura indipendente di generalizzazione. Non si attribuisce
al nostro baseline la capacità di leggere questo font reale: il suo risultato negativo è conservato.
Report, annotazioni, immagini canonica e annotata e licenza sono in `experiments/external_comparison/`.

## Roboflow: stato reale disponibile

La repository [roboflow/blackjack-basic-strategy](https://github.com/roboflow/blackjack-basic-strategy)
è stata consultata al commit `604d7a0b0c6d9a16e17048e38dfa559150c341a5`, con
[MIT](https://github.com/roboflow/blackjack-basic-strategy/blob/604d7a0b0c6d9a16e17048e38dfa559150c341a5/LICENSE).
Il codice fa riferimento al modello `playing-cards-ow27d/1`; la pagina primaria
[Playing Cards di Augmented Startups](https://universe.roboflow.com/augmented-startups/playing-cards-ow27d)
mostra il checkpoint pubblico `/4` e una licenza Public Domain per il dataset. Questi dati non
costituiscono una licenza o un hash di pesi scaricati e non provano metriche nel nostro benchmark.

Non abbiamo pesi locali fissati, `inference_sdk` o `ROBOFLOW_API_KEY`. Il report `roboflow-status.json`
è **unavailable**, `benchmark_executed=false`, metriche null. Non è stata inviata alcuna immagine
a endpoint remoto e non sono state copiate metriche pubblicitarie del provider. Un eventuale run
hosted deve usare credenziali dell'utente da variabili d'ambiente e un'autorizzazione esplicita
alla trasmissione delle immagini. L'alternativa locale richiede pesi, licenza e hash verificati.

## Riproduzione

Dal root del prodotto, con Python dell'ambiente BJLab:

```powershell
python experiments/acquire_external.py tray --dest ../../work/external-tray-3d7ab1bf
python -m bjlab.external_tray_benchmark ../../work/external-tray-3d7ab1bf experiments/external_discard_tray
python experiments/acquire_external.py martin --dest ../../work/external-martin-5145a126
python experiments/external_comparison/run_martin.py --source-dir ../../work/external-martin-5145a126 --output-dir experiments/external_comparison
python -m pytest tests/test_external_tray_benchmark.py -q
```

I cinque test del benchmark hanno passato in 0,70 secondi: misura dai pixel e invarianza di scala,
base assente e dorso non supportato, banda separata dal predictor, extrapolazione, geometria invalida
e denominatore che conserva le misure fallite. Le latenze dei report dipendono dall'host e non
sono SLA. Le immagini originali vanno acquisite separatamente; il bundle contiene report e preview.
