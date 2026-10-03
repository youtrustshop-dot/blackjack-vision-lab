import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const locale=await loadSource('i18n.ts');
test('English is default and covers navigation, action labels and network errors',()=>{
 assert.equal(locale.getLanguage(),'en');assert.equal(locale.t('Tavolo & decisioni'),'Table & decisions');
 assert.equal(locale.t('Carta'),'Hit');assert.equal(locale.t('Condividi finestra o schermo'),'Share window or screen');
 assert.match(locale.t('Il backend locale non risponde. Per questa pagina avvia run.ps1 dalla cartella dei sorgenti, oppure apri l’app desktop.'),/^The local backend/);
});
test('Italian is selectable for new English features and legacy labels',()=>{
 locale.setLanguage('it');assert.equal(locale.t('Share screen'),'Condividi schermo');assert.equal(locale.t('Table & decisions'),'Tavolo & decisioni');
 assert.equal(locale.t('Estimated EV'),'EV stimato');assert.equal(locale.t('Nuova sessione'),'Nuova sessione');locale.setLanguage('en');
});
test('dynamic fragment spacing and technical values survive localization',()=>{
 assert.equal(locale.t(' mazzi · '),' decks · ');assert.equal(locale.t(' /api/live '),' /api/live ');assert.equal(locale.t('Hi-Lo'),'Hi-Lo');
 assert.equal(locale.t('6 mazzi · 23 carte osservate'),'6 decks · 23 observed cards');
 assert.equal(locale.t('5.54 mazzi fisici rimasti'),'5.54 physical decks remaining');
 assert.equal(locale.t('Round 5 · unità di puntata'),'Round 5 · wager units');
 assert.equal(locale.t('Puntata 2'),'Wager 2');
});
