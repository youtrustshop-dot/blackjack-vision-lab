# Blackjack Vision Lab

Laboratorio open source locale per simulazioni di blackjack, visione video continua, conteggio delle carte e analisi matematica. L'inglese è la lingua principale; seleziona **Italiano** per l'interfaccia secondaria.

[Installer e ZIP Windows 1.0.0](https://github.com/youtrustshop-dot/blackjack-vision-lab/releases/tag/v1.0.0) · [Documentazione principale in inglese](README.md).

## Prova subito

1. Apri **Visione live → Avvia demo del laboratorio**: il bot gioca e l'osservatore legge soltanto il video.
2. Per il tuo schermo, apri l'app locale in Chrome o Edge e premi **Condividi schermo**. Scegli finestra, scheda o schermo nel selettore del browser. La lettura continua automaticamente.
3. **Apri finestra simulatore** offre un tavolo separato. Condividilo e seleziona i quattro angoli del tavolo: alto sinistra, alto destra, basso destra, basso sinistra.
4. **Consigliere flottante** mostra azione, probabilità, EV e conteggio. Il consiglio scompare quando il video o le carte non sono affidabili.

Il riconoscimento è validato sulla grafica delle carte del laboratorio. Altri giochi e fotografie richiedono un detector verificato. Il conteggio è completo soltanto quando l'osservazione parte da un nuovo shoe.

Le probabilità live e gli EV sono stime Monte Carlo su pool finito, con strategia basic generata per la continuazione. Vittoria/parità/sconfitta riguardano il profitto della mano attiva e dei nuovi split; le altre mani già presenti sono escluse. L'intervallo statistico non misura l'errore percettivo. Laya rimane rinviato.

Da sorgente, Python 3.12+ e Node 22+: esegui `setup.ps1`, poi `run.ps1`; apri http://127.0.0.1:8765 e tieni il backend avviato. Il pacchetto Windows include il backend e non richiede Python o Node. Licenza MIT per il codice originale.

La versione 1.0 aggiunge configurazione guidata, modalità semplice/standard/personalizzata, 1–8 mazzi selezionabili, cinque tavoli indipendenti, immagini incollate/trascinate/caricate, asso 1/11 e tutte le 550 combinazioni iniziali. Per ogni stato giocabile valido propone subito una mossa legale; se la stima EV non separa le azioni mantiene la strategia base. La grafica principale e le immagini GitHub sono in inglese.

È uno strumento di analisi e formazione, non un consiglio finanziario e non un sistema che garantisce vittorie. Poker è solo monitoraggio video; Clef è un classificatore opzionale separato.
