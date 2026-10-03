import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {parseCardInput}=await loadSource('card-input.ts');
test('blank placeholders never become a single empty card',()=>{
 assert.throws(()=>parseCardInput('','Player cards',2,24),/at least two player cards/);
 assert.throws(()=>parseCardInput('  ','Dealer upcard',1,1),/one dealer upcard/);
 assert.deepEqual(parseCardInput('','Observed cards'),[]);
});
test('common card separators, Unicode suits and ace aliases work',()=>{
 assert.deepEqual(parseCardInput('7♠, 2♣','Player cards',2,24),['7','2']);
 assert.deepEqual(parseCardInput('asso + t; Kd','Player cards',2,24),['A','10','K']);
});
test('ambiguous ranks and multiple dealer cards are rejected before the API',()=>{
 assert.throws(()=>parseCardInput('72 6','Player cards',2,24),/unrecognized card/);
 assert.throws(()=>parseCardInput('6 7','Dealer upcard',1,1),/exactly one/);
});
