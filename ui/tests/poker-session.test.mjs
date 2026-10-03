import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {PokerSession}=await loadSource('poker-session.ts');
const frame=(hole,board)=>({hole,board,gate:{solver_allowed:true,reasons:[]}});
test('three stable observations append one event; turn extends flop',()=>{
 const session=new PokerSession(),flop=frame(['AS','KH'],['QS','JH','2D']);
 assert.equal(session.observe(flop,1).gate.solver_allowed,false);
 session.observe(flop,2);assert.equal(session.observe(flop,3).gate.solver_allowed,true);
 session.observe(flop,4);assert.equal(session.events.length,1);
 const turn={...flop,board:[...flop.board,'3C']};
 for(let i=0;i<3;i++)session.observe(turn,5+i);
 assert.equal(session.events.length,2);
 assert.equal(session.observe({...flop,board:['4S','5S','6S']},8).gate.solver_allowed,false);
});
test('empty board is an explicit preflop declaration and new hands do not reuse old board',()=>{
 const session=new PokerSession(),preflop=frame(['AS','KH'],[]);
 for(let i=0;i<3;i++)assert.equal(session.observe(preflop,i).gate.solver_allowed,false);
 assert.equal(session.observe(preflop,4,true).gate.solver_allowed,true);
 const next=frame(['2S','3D'],['4S','5S','6S']);
 for(let i=0;i<3;i++)session.observe(next,5+i);
 assert.equal(session.round,2);assert.deepEqual(session.events.at(-1).hole,next.hole);
});
