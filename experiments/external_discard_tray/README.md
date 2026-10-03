# Discard tray reale: risultato negativo conservato

`benchmark-report.json` è il run prudente finale: 9/9 test normali e 7/7 overflow
richiedono astensione per segnale del dorso fuori supporto. Metriche d'errore null;
non è una validazione riuscita.

`initial-unsafe-zero-report.json` conserva il primo run numerico errato: trattava
assenza del blu come vuoto e produceva MAE296/343,43 carte. Il codice archiviato
`initial-runner-source.txt` ha lo stesso SHA-256 del runner originale nel report.
Questo archivio documenta il difetto, non è il predictor operativo.

`protocol.json`, `frozen-model.json`, `source-manifest.json` e `SOURCE_LICENSE.txt`
fissano provenienza, split cronologico, parametri, hash e licenza. Una sola sequenza
non valuta generalizzazione tra sessioni. Originali pinned in `work`, fuori dal bundle.
Vedere `docs/EXTERNAL_BENCHMARKS.md` per metodologia, limiti e comandi riproducibili.
