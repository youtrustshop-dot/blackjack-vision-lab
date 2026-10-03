# Validazione delle stime di mazzi e vassoio

La validazione eseguibile è `bjlab.shoe_inference_benchmark`. Genera shoe fisici uniformemente
mescolati e immagini originali di un vassoio controllato; osservazioni e label sono separate.
Non usa fotografie esterne né immagini senza licenza. Le immagini del vassoio non contengono font
o testo con il numero di carte. La fonte di riferimento tipografica è dichiarata soltanto come
riferimento non utilizzato: [DejaVu 2.37](https://github.com/dejavu-fonts/dejavu-fonts/releases/tag/version_2_37),
commit `0eda8a319c08835009849583cd090bb5b141ce25`, con
[licenza originale](https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/version_2_37/LICENSE).
I dati generati seguono la licenza del repository. I manifest fissano seed, hash del generatore e
dell'estimatore, hash SHA-256 di ogni PNG; il report fissa anche manifest e runner effettivo.

```powershell
python -m bjlab.shoe_inference_benchmark generate experiments/shoe_inference/dataset --sessions 50 --seed 29
python -m bjlab.shoe_inference_benchmark run experiments/shoe_inference/dataset --output experiments/shoe_inference/benchmark-report.json
```

L'esecuzione reale ha generato **50 sessioni e 372 PNG**, con split temporale: prime 30 sessioni train,
successive 10 calibration, ultime 10 test. Lo split respinge leakage o sessioni train/calibration
posteriori al test. I checkpoint all'interno dello stesso shoe sono correlati: 48 risultati della
stima mazzi provengono da dieci shoe test, non da 48 esperimenti indipendenti.

## Distribuzione dei mazzi

Ogni shoe ha D∈{1,2,4,6,8}, bilanciato tra sessioni. La sua sequenza fisica è mescolata con seed;
l'estimatore riceve solo ID logici, rank e suit osservati, senza D vero. Nel 20% dei campioni manca
il suit. Si valuta a 8,16,32,52,80 carte osservate, limitando i checkpoint alla dimensione reale.
Prior uniforme e likelihood senza reinserimento restano assunzioni dichiarate del modello.

Il report reale sui 48 checkpoint test mostra accuracy **47,92%**, Brier multiclass **0,6450**,
ECE **0,1132**, massimo posteriore medio **45,69%**, entropia media **1,6368 bit**. Questi risultati
dimostrano che le informazioni parziali lasciano ambiguità sostanziale; non permettono una scelta
certa del numero di mazzi. Il report include distribuzione completa e metriche per checkpoint.
Il mazzo noto del simulatore deve restare una dichiarazione separata dall'estimatore visuale.

## Vassoio: pixel, misura, calibrazione

Il renderer genera una pila chiara con altezza fisica controllata, diversi zoom, due fondali e rumore.
`measure_discard_tray(image)` trova la pila dai pixel e misura il rettangolo. Normalizza l'altezza
con la larghezza visibile rispetto a un riferimento controllato di 150 pixel; non riceve la label.
`DiscardTrayCalibrator.fit` apprende altezza/intercetta sulle sole sessioni train. L'intervallo usa
il quantile dei residui delle sessioni calibration, prima di leggere il test. È un intervallo empirico,
non una probabilità e non una garanzia sotto correlazione o cambiamento di distribuzione.

Sui **62 frame test del renderer controllato**, MAE **0,3150 carte**, p95 dell'errore **0,6394 carte**,
copertura degli intervalli **96,77%**; p95 della latenza misurata **10,34 ms** sull'host di questa
esecuzione. Il benchmark include un secondo holdout con spessore delle carte aumentato del 15%,
mai visto nel fit: MAE **13,8713 carte**, p95 **46,0814 carte**, copertura **0%**. Il cambiamento rende
quindi inaffidabile la calibrazione originaria, anche quando il rettangolo viene rilevato correttamente.

Il vassoio resta sperimentale e separato dal conteggio confermato delle carte. Servono immagini reali,
calibrazione del proprio vassoio/camera, condizioni di inclinazione/occlusione e sessioni fisiche
future per una validazione esterna. Nessun risultato sintetico viene presentato come prova su foto
reali. Quando il setup cambia, la stima non va incorporata automaticamente nella composizione o EV.

## Prove e artefatti

`tests/test_datasets.py` e `tests/test_shoe_inference_benchmark.py` hanno completato nove test con
exit 0, inclusi conteggio delle sole facce visibili, misura dai pixel, normalizzazione zoom, calibrazione,
split temporale e degradazione sotto cambiamento di spessore. L'host ha emesso un errore nativo WMI
del plugin Hypothesis durante il riepilogo terminale; le assertion erano terminate e il runner ha
comunque riportato nove pass con exit 0. Il benchmark successivo è terminato senza quel messaggio,
con status completed e report persistito. La suite generale del progetto rimane una verifica distinta.
