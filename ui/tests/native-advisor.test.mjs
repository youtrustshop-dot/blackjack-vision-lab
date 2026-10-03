import test from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {evidenceExpiry}=await loadSource('advisor-evidence.ts');

test('external view retains the original evidence deadline through redraw and network latency',()=>{
 assert.equal(evidenceExpiry(1000,100,350),1100);
 assert.equal(evidenceExpiry(750,350,500),1100);
 assert.equal(evidenceExpiry(100,100,500),500);
});
