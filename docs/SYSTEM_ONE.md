# Esperimenti System One: fase osservabile, separata dalla strategia

`bjlab.model_experiments` confronta una baseline deterministica con adattatori opzionali Laya e Jev
su sei fasi: DEALING, PLAYER_TURN, DEALER_TURN, ROUND_END, SHUFFLING, UNCERTAIN. Nessun modello sceglie
hit/stand/double/split, puntate o EV. Non viene importato dal solver: rimane un esperimento isolato.

L'input contiene soltanto carte osservate, etichette dei controlli, testo osservato, quantità normalizzata
di movimento, problemi di integrità e precedente numero visibile di carte. Una carta coperta non può
contenere rank/seme segreti. `PhaseObservation.from_dict` respinge campi sconosciuti, compresi label/phase.
`observation_from_perception` costruisce l'input da detection e testo, senza accettare uno stato vero
del simulatore. Il benchmark conserva label e sessione nella riga esterna e passa al modello esclusivamente
il sotto-oggetto observation.

## Dataset e protocollo

Il generatore produce fixture sintetiche di caratteristiche osservabili, con seed e intere sessioni
disgiunte tra train/calibration/test. Sono un benchmark del classificatore di fase, non una misura della
vision sui pixel. Per un esperimento completo si devono aggiungere input derivati realmente da video
e label del simulatore conservate separatamente. `contract_fixture.jsonl` è una piccola fixture manuale
per verificare schema/SDK; non viene spacciata per un campione reale o casuale.

```powershell
python -m bjlab.model_experiments generate experiments/system_one/phase_dataset.jsonl --sessions 20 --variants 3 --seed 17
python -m bjlab.model_experiments run experiments/system_one/phase_dataset.jsonl --model baseline --output experiments/system_one/baseline-report.json
```

Il report contiene accuracy, matrice di confusione, Brier multiclass, ECE, NLL, p50/p95 delle latenze,
fallimenti per caso, frazione di errori d'inferenza e risultati individuali. Brier è la media della somma
sulle sei classi, nell'intervallo [0,2]. ECE usa la probabilità della classe selezionata, non una confidence
di significato diverso. NLL usa un floor numerico 1e-15, dichiarato dal codice. Con `--warmup 1` il caricamento
non entra nella latenza; con warmup 0 il report segnala che include il cold start.

Gli errori d'inferenza non spariscono: `accuracy_all_cases` li penalizza e lo stato diventa partial_failure.
Una dipendenza, un checkpoint o una chiave mancanti producono unavailable e metrics null. Il comando
termina con codice 2 per esecuzioni non completate. Non sono stati inventati risultati per i modelli
opzionali. Anche le probabilità one-hot della baseline rappresentano una regola deterministica, senza
assunzione di calibrazione sul dominio. Temperature o soglie future vanno apprese su calibration e
misurate su test; il framework non attribuisce calibrazione Blackjack alle dichiarazioni di un vendor.

## Laya opzionale, API verificata

L'adattatore carica lazily `laya.load(checkpoint)` e invoca `agent.predict(state, questions)` con una
domanda Choice e sei criteri. Legge `result["answers"]["phase"]`, inclusi choice e probabilities. Questo
contratto segue il [README del checkpoint](https://github.com/he-jev/laya) e il
[SDK originale](https://github.com/NandhaKishorM/laya). Il modello e il SDK hanno cicli di release distinti;
salvare la versione effettivamente usata e il checkpoint nel report sperimentale.

```powershell
# Dipendenza opzionale, da installare soltanto per l'esperimento.
python -m pip install laya
python -m bjlab.model_experiments run experiments/system_one/phase_dataset.jsonl --model laya --allow-download --warmup 1 --output experiments/system_one/laya-report.json
```

Per checkpoint già presente: `--local-checkpoint PATH`, senza `--allow-download`. Il default non importa
Laya né scarica pesi. La disponibilità del pacchetto non equivale alla validazione del modello; tempi,
accuratezza e calibrazione vengono misurati soltanto durante una reale esecuzione. Eventuali errori di
runtime/caricamento restano fallimenti, senza sostituire silenziosamente Laya con la baseline.

## Jev opzionale, servizio ufficiale

L'adattatore usa il pacchetto ufficiale `typesafe-sdk`, modulo `typesafe_sdk`, e
`TypeSafeClient.system_one(state=..., questions=...)`. La risposta typed viene letta da
`response.choices["phase"]`. Le credenziali provengono da `TYPESAFE_API_KEY`; il client usa il servizio
ufficiale predefinito e un timeout esplicito. Fonti primarie:
[installazione e chiamata SDK](https://docs.typesafe.ai/sdk/python),
[client sincrono](https://docs.typesafe.ai/sdk/python/api/clients/sync),
[risposte tipizzate](https://docs.typesafe.ai/sdk/python/api/types/responses).

```powershell
python -m pip install typesafe-sdk
# TYPESAFE_API_KEY deve già essere impostata in modo sicuro; il framework non stampa la chiave.
python -m bjlab.model_experiments run experiments/system_one/phase_dataset.jsonl --model jev --allow-network --warmup 1 --output experiments/system_one/jev-report.json
```

`--jev-model NAME` seleziona una versione esplicita; senza parametro si registra il modello effettivo
restituito dal servizio. Non vengono creati account, comprati crediti o inviati dati automaticamente.
Una chiamata remota richiede un'esecuzione esplicita con rete e una credenziale già disponibile.
Le eccezioni SDK vengono registrate per tipo senza includere messaggi che potrebbero contenere segreti.

## Verifica richiesta

`tests/test_model_experiments.py` verifica determinismo/split, rifiuto di leakage, metriche, probabilità
malformate, errori d'inferenza, assenza di credenziali e i contratti degli adattatori tramite mock.
I mock dimostrano solo la compatibilità del codice con quei contratti, non accuratezza o latenza dei
modelli reali. Il comando di test combinato con la calibrazione ha completato 30 test con successo.
È stato generato `experiments/system_one/phase_dataset.jsonl`: 360 casi, seed 17, venti sessioni,
con 72 casi test in sessioni successive. `baseline-report.json` proviene da una esecuzione reale della
baseline con warmup 1. I benchmark opzionali Laya/Jev non sono stati eseguiti: richiedono runtime/pesi
o credenziali e devono conservare questa distinzione anche nei report futuri.
