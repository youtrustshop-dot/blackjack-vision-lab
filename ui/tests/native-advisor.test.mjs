import test from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {evidenceExpiry}=await loadSource('advisor-evidence.ts');
const {compactAdvisor,advisorSnapshotCurrent}=await loadSource('compact-advisor.ts');

test('external view retains the original evidence deadline through redraw and network latency',()=>{
 assert.equal(evidenceExpiry(1000,100,350),1100);
 assert.equal(evidenceExpiry(750,350,500),1100);
 assert.equal(evidenceExpiry(100,100,500),500);
});

const report=()=>({source_id:'source-1',state_id:'source-1:4:hand',player:['A','5'],dealer:['2'],phase:'player',gate:{solver_allowed:true,reasons:[]},advice:{best_action:'hit'},count_reliable:false,true_count:null});

test('current usable hand stays actionable with incomplete session count and shows both ace values',()=>{
 const value=compactAdvisor(report(),false);
 assert.equal(value.action,'HIT');assert.equal(value.status,'LIVE');assert.equal(value.total,16);
 assert.equal(value.hard,6);assert.equal(value.soft,true);assert.equal(value.hasAce,true);
 assert.equal(value.count,'R2 · COUNT UNVERIFIED');
});

test('stale action and certified count are withheld together despite retained evidence',()=>{
 const value=compactAdvisor({...report(),count_reliable:true,true_count:2.5},true);
 assert.equal(value.action,null);assert.equal(value.status,'STALE');
 assert.equal(value.display,'STALE');
 assert.equal(value.count,'R2 · COUNT UNVERIFIED');assert.deepEqual(value.player,['A','5']);
});

test('blocked, unsupported or incomplete observation cannot render a confident action',()=>{
 for(const patch of [{gate:{solver_allowed:false,reasons:['Unreadable card']}},{player:['5']},{player:['A','?']},{dealer:['?']},{dealer:['2','7']},{advice:{best_action:'nonsense'}}]){
  const value=compactAdvisor({...report(),...patch},false);
  assert.equal(value.action,null);assert.equal(value.status,'UNCERTAIN');
  assert.equal(value.display,'CHECK TABLE');
 }
});

test('WAIT is reserved for an observed idle phase rather than an unreadable player hand',()=>{
 for(const phase of ['waiting','dealing','dealer','settled'])assert.equal(compactAdvisor({...report(),phase,advice:null,gate:{solver_allowed:false}},false).display,'WAIT');
 const value=compactAdvisor({...report(),player:['1','5'],advice:null,gate:{solver_allowed:false}},false);
 assert.equal(value.hasAce,false);assert.equal(value.display,'CHECK TABLE');
});

test('compact view retains correct hard ace total and the existing action vocabulary',()=>{
 for(const [action,label] of [['hit','HIT'],['stand','STAND'],['double','DOUBLE'],['split','SPLIT'],['surrender','SURRENDER']]){
  const value=compactAdvisor({...report(),player:['A','5','9'],advice:{best_action:action}},false);
  assert.equal(value.action,label);assert.equal(value.total,15);assert.equal(value.soft,false);
 }
});

test('native view binds table, source and state rather than accepting a previous table report',()=>{
 const value={source_id:'source-1',report:report(),stale:false};
 const host={available:true,stream_id:'stream-1',tables:[{stream_id:'stream-1',source_id:'source-1'}]};
 assert.equal(advisorSnapshotCurrent(value,host,'stream-1'),true);
 assert.equal(advisorSnapshotCurrent({...value,report:{...report(),state_id:null,advice:null,gate:{solver_allowed:false}}},host,'stream-1'),true);
 assert.equal(advisorSnapshotCurrent({...value,report:{...report(),state_id:null}},host,'stream-1'),false);
 for(const [state,status,stream] of [[value,host,'stream-2'],[value,{...host,available:false},'stream-1'],[value,{...host,tables:[]},'stream-1'],[{...value,source_id:'other'},host,'stream-1'],[{...value,report:{...report(),state_id:'source-2:4:hand'}},host,'stream-1'],[{...value,stale:true},host,'stream-1'],[null,host,'stream-1']]){
  assert.equal(advisorSnapshotCurrent(state,status,stream),false);
 }
});
