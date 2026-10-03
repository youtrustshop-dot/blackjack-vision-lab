# Studio temporal holdout

`dataset/manifest.json` descrive 372 PNG prodotti dal generatore reale, seed 29, cinquanta sessioni.
Il repository pubblico conserva il manifest e i report; le immagini possono essere rigenerate.
`benchmark-report.json` è il risultato dell'esecuzione reale successiva, con hash di dati e runner.

I valori riassuntivi e i limiti sono in `docs/SHOE_INFERENCE.md`. Train, calibration e test sono
intere sessioni cronologiche. Il test contiene anche uno spessore delle carte mai visto: la copertura
cala a zero; questo fallimento sperimentale viene conservato nel report.

I risultati riguardano scene originali controllate e non validano fotografie di vassoi fisici.
