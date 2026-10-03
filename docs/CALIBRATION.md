# Calibrazione geometrica e lettura delle etichette

La calibrazione geometrica opera solo sui pixel e sui quattro angoli scelti dal chiamante.
`NormalizedROI` valida rettangoli normalizzati in [0,1], li converte in pixel e ritaglia immagini RGB.
`controlled_table_zones()` fornisce regioni modificabili per banco, giocatore, regole e controlli.

```python
from bjlab.calibration import normalize_table, NormalizedROI
from bjlab.vision import TemplateCardDetector

calibrated = normalize_table(
    "local-table.png",
    corners=[(50, 40), (340, 65), (320, 260), (75, 240)],
    outputsize=(960, 600),
)
canonical_detections = TemplateCardDetector().detect(calibrated.image_rgb)
source_detections = [calibrated.map_detection_to_source(d) for d in canonical_detections]
```

Gli angoli devono essere TL,TR,BR,BL, in senso orario nelle coordinate immagine (y verso il basso).
Non si riordinano automaticamente punti arbitrari. Coordinate non finite, fuori immagine, quadrilateri
concavi/incrociati, lati duplicati o troppo corti e trasformazioni instabili sono respinti. Con
`corners_normalized=True`, gli angoli in [0,1] vengono convertiti in coordinate dei pixel estremi.
La homography mappa il quadrilatero alla dimensione canonica; l'inversa riporta punti e detection
nell'immagine sorgente. Un bounding box riportato è il rettangolo assiale che contiene i quattro
angoli trasformati. Per disegnare l'esatta prospettiva usare `map_points_to_source` sui quattro angoli.
`CalibratedFrame.to_dict()` serializza dimensioni, angoli, matrice e inversa, senza codificare i pixel.

I test inclusi controllano ROI, immagine checkerboard identica, un quadrilatero noto, mapping inverso,
contenimento dei bounding box e rifiuto di configurazioni invalide. La trasformazione corregge il piano
del tavolo; non garantisce di recuperare un testo già troppo piccolo, mosso, occluso o fuori piano.

## Regole e bottoni dai pixel

Il renderer accetta `rule_labels` e `button_labels`, che disegnano realmente le parole. Il detector
non riceve quei parametri: `extract_controlled_metadata(image)` confronta i pixel con un vocabolario
pubblico fisso di template. Le regole supportate sono H17/S17, AHC/ENHC, PEEK/NPEEK,
DAS/NDAS, RSA/NRSA, ES/LS/NS, BJ3:2/BJ6:5 e D1/D2/D4/D6/D8; i controlli sono
HIT/STAND/DOUBLE/SPLIT/SURRENDER/DEAL/NEW SHOE/INSURANCE/DECLINE INSURANCE/CONTINUE.
`hole_card` e `peek` sono campi separati; le vecchie fixture con il solo PEEK mantengono
la compatibilità sul campo `hole_card`. DECLINE INSURANCE non crea il bottone INSURANCE
solo perché contiene quella parola.

```python
from bjlab.datasets import render_table
from bjlab.calibration import extract_controlled_metadata

frame = render_table([], rule_labels=["H17", "ENHC", "DAS", "RSA", "LS", "BJ3:2", "D6"],
                     button_labels=["HIT", "STAND", "DOUBLE"])
observed = extract_controlled_metadata(frame)
```

Una parola assente lascia il campo null. Due etichette incompatibili producono un problema esplicito
e il campo null. Le detection includono bounding box e similarità grezza; non una probabilità calibrata
di correttezza delle regole. È un riconoscitore del testo del renderer, con font/dimensione canonici,
non OCR generico. `TemplateTextDetector` permette vocabolario, font e ROI diversi, che devono essere
validati con nuovi dati. I template non possono inferire regole che nessun pixel mostra.

## OCR opzionale reale

`TesseractAdapter` usa un eseguibile Tesseract locale realmente presente, con output TSV, ROI, lingua,
page-segmentation mode e timeout. In assenza dell'eseguibile fallisce esplicitamente. Non installa
software automaticamente e non restituisce un falso risultato. La confidence TSV viene dichiarata
`tesseract_score_not_calibrated_probability`. Errori del processo e timeout rimangono visibili al chiamante.
Tesseract è un'estensione opzionale: non è stata dichiarata una validazione OCR senza runtime e dati.

## Stato della verifica

Il comando `python -m pytest tests/test_calibration.py tests/test_model_experiments.py -q` ha completato
30 test con successo. Comprende geometria, mapping inverso, tre temi visuali, etichette assenti e
contraddittorie e il rifiuto di OCR opzionale mancante. L'esecuzione iniziale aveva evidenziato un
arrotondamento floating-point della ROI e marcatori simili D6/D8 sullo stesso token: ora gli epsilon
agiscono solo sotto il miliardesimo di pixel e le etichette competono sullo stesso bounding box.
Alternative con punteggi quasi uguali restano ambigue; la soglia assoluta resta 0,92.

L'estensione successiva di regole e controlli assicurazione ha passato tutti i 19 test
di `tests/test_calibration.py` in 1,84 secondi. Nessuna regola viene letta dallo stato interno.
