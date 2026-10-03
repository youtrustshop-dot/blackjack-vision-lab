# Confronto esterno su fixture Martin

Run reale su club1, commit MIT5145a126, stessa homography per entrambi i detector:
baseline renderer BJLab0/13 carte, Martin originale13/13 detection e ranghi corretti.
L'algoritmo Martin non riconosce il seme. Una sola fixture del progetto dei template
non è un holdout indipendente e non misura robustezza generale.

`martin-annotation.json` conserva truth e geometria scelti prima dell'inferenza.
`martin-comparison-report.json` conserva detection, metriche e checksum. Preview
e copyright sono inclusi. `run_martin.py` carica solo il modulo revisionato da `work`,
con due adattamenti di compatibilità dichiarati; non incorpora codice esterno nel core.

`roboflow-status.json` è unavailable, benchmark non eseguito e metriche null.
SDK, credenziali e pesi locali verificati assenti; nessuna chiamata remota effettuata.
Vedere `docs/EXTERNAL_BENCHMARKS.md` per fonti e riproduzione.
