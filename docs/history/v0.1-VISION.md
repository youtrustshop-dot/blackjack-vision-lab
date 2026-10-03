# Percezione, identità temporale e replay

Il percorso eseguibile è `pixel RGB → TemplateCardDetector → TemporalTracker → EventLog → ReplayState`.
Il detector riceve soltanto immagini. Il simulatore e il benchmark conservano la verità separata;
gli ID delle etichette vengono usati dal valutatore dopo il matching geometrico, mai dal detector.

## Contratto visuale controllato

`bjlab.datasets.render_table(cards, theme="green", width=960, height=600, card_design="classic")` restituisce una immagine Pillow.
Ogni elemento contiene `rank`, `suit`, `x`, `y`; accetta anche `face_down`, `visible`, `scale`, `occlusion`.
`card_id` e `zone` non vengono codificati nei pixel. Una carta coperta nasconde rank e suit anche se il
simulatore li conosce. Il renderer usa carte avorio di 78×110 pixel, rank nell'angolo (9,7), font bold 22,
marcatore del seme ASCII S/H/D/C in (9,35), font bold 17. I simboli decorativi sono vettoriali.
Il font predefinito è Arial Bold su Windows, DejaVu/Liberation quando disponibili altrove.
`card_design` accetta `classic` e `minimal`: cambia soltanto la decorazione centrale,
preservando i marcatori degli angoli e la geometria utilizzata dal detector. Il valore
predefinito resta `classic`; un test legge realmente 52 rank/semi per ciascuno dei due design.

La baseline OpenCV trova rettangoli chiari, normalizza le dimensioni, estrae i due marcatori e confronta
le forme con template costruiti con lo stesso font. Riconosce anche il retro blu. I test verificano tutte
le 52 combinazioni, tre scale e tre temi, lieve rumore, JPEG e un video locale MJPG.
La baseline non promette riconoscimento di layout esterni, prospettive arbitrarie o angoli completamente
coperti: questi casi richiedono dati e un modello dedicato. Un miss rimane un miss nel benchmark.

```python
from bjlab.datasets import render_table
from bjlab.vision import TemplateCardDetector, TemporalTracker

pixels = render_table([
    {"rank": "A", "suit": "S", "x": 100, "y": 80},
    {"rank": None, "suit": None, "face_down": True, "x": 200, "y": 80},
])
detector = TemplateCardDetector()
tracker = TemporalTracker(stable_frames=3)
tracker.new_shoe(6, timestamp=0)
for timestamp in (0.1, 0.2, 0.3):
    tracker.update(detector.detect(pixels), timestamp, round_id="round-1")
print(tracker.state_summary())
```

La sorgente PNG/JPEG è `detector.detect(path)`, quella video è `LocalVideoSource(path).frames()`;
ogni elemento restituisce `(timestamp_seconds, rgb_array)`. `LocalWindowCapture` è un adattatore opzionale
mss con rettangolo locale esplicito `{left, top, width, height}`. Non individua né controlla finestre terze.

## Identità di distribuzione

Il tracker conferma dopo N frame consecutivi con un punteggio sopra soglia. La conferma assegna un ID
logico persistente, distinto dalla singola osservazione visuale. Le carte rimangono associabili per tutta
la mano anche dopo uno spostamento o un'occlusione. Una carta coperta confermata è già una carta fisica;
`CARD_REVEALED` ne aggiorna il valore senza creare un'altra distribuzione. Una lettura corretta dopo N
frame produce `STATE_CORRECTION`, sostituendo il contributo al conteggio tramite replay.

Il chiamante deve fornire i confini della mano (`round_id`, `start_round`, `end_round`) e dello shoe.
Due carte identiche, rimosse e ridistribuite durante frame mai osservati, sono indistinguibili dai soli
pixel. Associazioni quasi equivalenti producono un problema persistente `STATE_UNCERTAIN`, da rivedere
con motivazione; l'applicazione non trasforma un ID di tracking in prova di identità fisica.

Carte non ancora stabili o temporaneamente assenti rendono il gate `provisional`. Un'identità ambigua,
un track perso o una violazione di conservazione richiedono `manual_review`. L'UI può usare
`state_summary()["gate"]["solver_allowed"]`. `probability_of_correct_state` resta null: non esiste una
probabilità di integrità dello shoe inventata moltiplicando i punteggi delle carte.

## Eventi e conservazione

`EventLog.append(kind, payload, timestamp)` valida prima di modificare il journal. Gli eventi sono
dataclass immutabili; `.payload` restituisce una copia JSON. Una hash chain SHA-256 rileva modifiche o
riordini nel file. Non è una firma e non dimostra chi abbia prodotto il journal.

- `NEW_SHOE` dichiara l'ID e un numero noto di mazzi oppure null.
- `CARD_CONFIRMED` richiede un nuovo `card_id`; rank e suit possono essere null per carte coperte/bruciate.
- `CARD_REVEALED` aggiorna soltanto una carta precedentemente sconosciuta.
- `STATE_CORRECTION` richiede una motivazione; può correggere rank/suit o ritrattare un duplicato.
- `ROUND_STARTED`, `ROUND_ENDED`, `CARD_MOVED`, `TRACK_LOST`, `TRACK_REACQUIRED` preservano il contesto.
- `STATE_UNCERTAIN` e `STATE_REVIEWED` registrano e risolvono problemi con una traccia verificabile.

Con mazzi noti, ogni append controlla carte fisiche ≤52D, ogni rank ≤4D e ogni coppia rank/seme ≤D.
Gli eventi illegali sono respinti atomicamente. `save(path)` esporta JSONL schema v1; `load(path)` verifica
schema, sequenza, tempo monotono, digest e conservazione. `replay(to_index)` ricostruisce fino all'indice
inclusivo; -1 restituisce lo stato vuoto e null lo stato corrente. Lo stato restituito è una copia.
I nuovi shoe svuotano lo stato corrente conservando integralmente gli eventi storici.

`physical_remaining` sottrae tutte le carte distribuite, incluse quelle coperte. `composition_remaining`
ha dieci categorie A,2,…,9,10 ed è il pool informativo dopo avere sottratto solo i rank conosciuti.
Include carte coperte/bruciate sconosciute: il solver deve marginalizzare sulle loro identità e sul peek,
senza presentarlo come composizione esatta del mucchio fisicamente pescabile.

## Confidenza e stima dei mazzi

`CardDetection.score` è una similarità grezza, dichiarata da `score_type`, senza probabilità implicita.
`ScoreCalibrator` stima frequenze di correttezza per bin con Laplace smoothing e supporto esplicito;
un bin senza campioni restituisce null. Il fit usa sessioni di calibrazione separate. La valutazione
riporta Brier score, ECE e campioni privi di supporto. I falsi positivi entrano come risultati errati,
non vengono esclusi per migliorare la calibrazione. Il calibratore serializzabile riguarda la singola
detection, mai l'integrità dell'intera sessione.

`DeckCountEstimator` mantiene P(D) per D∈{1,2,4,6,8}. Usa molteplicità rank/seme e una likelihood di
estrazione uniforme senza reinserimento; ID ripetuti sostituiscono l'osservazione anziché aggiungere
carte. Due A♠ eliminano D=1, senza scegliere arbitrariamente un unico altro valore. Restituisce prior,
numero di osservazioni, entropia, massimo posteriore e assunzioni. La certezza assoluta resta false:
il campione non prova che la lista dei candidati o il modello di selezione siano completi.

`estimate_discard_tray` converte un'altezza in pixel mediante calibrazione esplicita e propaga un
intervallo di errore. Rimane sperimentale, non una probabilità e non viene automaticamente sommato
all'evidenza delle carte osservate. Servono fotografie etichettate di vassoi per validarlo realmente.

## Dataset e benchmark riproducibili

```python
from bjlab.datasets import generate_dataset, benchmark_dataset, benchmark_tracking_dataset
from bjlab.vision import TemplateCardDetector, ScoreCalibrator

generate_dataset("dataset", sessions=18, frames_per_session=6, seed=13)
detector = TemplateCardDetector()
calibration = benchmark_dataset("dataset", detector, split="calibration")
fit_samples = [(row["score"], row["correct"]) for row in calibration["raw_score_labels"]]
calibrator = ScoreCalibrator().fit(fit_samples)
test = benchmark_dataset("dataset", detector, split="test")
print(calibrator.evaluate((row["score"], row["correct"]) for row in test["raw_score_labels"]))
print(benchmark_tracking_dataset("dataset", detector, split="test"))
```

Il manifest contiene seed, tema, sessione, frame, etichette e trasformazioni. Intere sessioni sono
disgiunte tra train/calibration/test. Il tema burgundy è presente soltanto nei test e soltanto nelle
sessioni già assegnate ai test. `validate_splits` blocca leakage tra sessioni, anche tra temi diversi.
Si generano movimento, carte coperte/rivelate, un'occlusione temporanea, lieve blur/rumore/luminosità.
Precision, recall, accuratezza rank/seme, falsi positivi, falsi negativi e latenza hanno denominatori
espliciti. Rank e suit usano soltanto facce con etichette note: un retro non può aumentare l'accuratezza
del rank perché null coincide con null. Classificazione dei retri ha precision/recall separate, incluse
carte perse e detection extra. Il benchmark temporale esegue la pipeline reale e misura eventi persi/duplicati/non associati,
deriva L1 dei rank e frazione di sessioni ricostruite correttamente. L'eleggibilità usa visibilità della
verità per N frame, indipendentemente dal successo del detector. Un detector vuoto ha eventi mancanti
e deriva non nulla nei test; non può ottenere un successo attraverso una scorciatoia al ground truth.

Il confronto effettivo di RC/TC, costo dello stato nativo e della pipeline pixel, conferma
temporale a uno/tre frame, gate e campioni di regret è documentato in
[PERCEPTION_EXPERIMENTS.md](PERCEPTION_EXPERIMENTS.md). Include risultati grezzi e ritardi,
senza usare astensioni come misure di regret zero.

## Estensione ONNX

`ONNXCardDetector` carica un file realmente esistente tramite onnxruntime opzionale; in assenza del
runtime/modello fallisce esplicitamente. Contratto: input float32 RGB `[1,3,H,W]` in [0,1], output
`[1,N,6]` con righe `[x1,y1,x2,y2,score,class_index]` nelle coordinate pixel dell'input; classi rank×seme
nell'ordine `RANKS × SUITS`, poi BACK. Include NMS. Non si dichiara compatibilità con tutti i formati
YOLO né un modello addestrato/validato che non sia stato fornito. Un modello esterno deve superare gli
stessi benchmark e la calibrazione separata prima di sostituire la baseline.
