import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {parseCorrection,readCorrections,differences}=await loadSource('replayCorrections.ts');
test('corrections keep original observation and identify added, changed, removed fields',()=>{
 const original={card:'7',confidence:.4},corrected=parseCorrection('{"card":"8","note":"manual"}');
 const diff=differences(original,corrected);
 assert.deepEqual(diff.map(x=>x.field),['card','confidence','note']);assert.equal(original.card,'7');
 assert.equal(diff[0].before,'7');assert.equal(diff[0].after,'8');
});
test('malformed and non-object corrections rejected',()=>{assert.throws(()=>parseCorrection('bad'));assert.throws(()=>parseCorrection('[]'));assert.throws(()=>parseCorrection('x'.repeat(30001)));});
test('correction history reload preserves revisions and refuses corruption',()=>{
 const revisions=[{frame:0,original:{card:'8H'},corrected:{card:'9H'},note:'Synthetic correction',createdAt:1}];
 assert.deepEqual(readCorrections(JSON.stringify(revisions)),revisions);assert.deepEqual(readCorrections(null),[]);
 for(const value of ['bad','{}','[null]',JSON.stringify([{...revisions[0],frame:-1}]),JSON.stringify([{...revisions[0],corrected:[]}]),JSON.stringify([{...revisions[0],createdAt:null}])])assert.throws(()=>readCorrections(value));
 assert.equal(revisions[0].original.card,'8H');
});
