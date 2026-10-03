# Esperimento classificazione della fase

Le istruzioni, i comandi e i limiti sono in `docs/SYSTEM_ONE.md`.

- `experiment.json`: protocollo e seed proposti.
- `contract_fixture.jsonl`: fixture manuale di schema/contratto SDK, con label separate.
- `phase_dataset.jsonl`: generare con il comando documentato; fixture sintetiche con seed 17.
- `*-report.json`: artefatti prodotti da esecuzioni reali, non inseriti con numeri presunti.

Il classificatore non può chiamare il solver né scegliere azioni di gioco. I modelli opzionali assenti
sono registrati unavailable, senza sostituire una validazione reale con un mock.
