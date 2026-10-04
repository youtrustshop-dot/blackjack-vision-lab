/** Browser UI contract test only: mocked native snapshots are not vision evidence. */
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
const require=createRequire(import.meta.url),pw=require(process.argv[2]);
const browser=await pw.chromium.launch({headless:true,channel:'chrome'});
const page=await browser.newPage({viewport:{width:260,height:185},reducedMotion:'reduce'});
const output=path.resolve(import.meta.dirname,'../../artifacts/advisor-compact/ui-contract');
fs.mkdirSync(output,{recursive:true});
const errors=[],controls=[],checks=[];page.on('pageerror',error=>errors.push(error.message));
let deadline=Date.now()+5000,offline=false;
const host={available:true,visible:true,topmost:true,stream_id:'stream-1',table_name:'Table 1',tables:[{stream_id:'stream-1',source_id:'source-1',table_name:'Table 1'}]};
const report={source_id:'source-1',state_id:'source-1:4:hand',player:['A','5'],dealer:['2'],phase:'player',gate:{solver_allowed:true,reasons:[]},advice:{best_action:'hit'},count_reliable:false,true_count:null};
await page.route('**/api/native/advisor/**',async route=>{
 if(offline){await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Local source disconnected.'})});return}
 const url=new URL(route.request().url());
 if(url.pathname.endsWith('/control')){
  const body=route.request().postDataJSON();controls.push(body);
  if(body.operation==='topmost')host.topmost=body.topmost;
  await route.fulfill({contentType:'application/json',body:'{"pending":true}'});return;
 }
 const value=url.pathname.endsWith('/status')?host:{report,source_id:'source-1',stale:false,evidence_ttl_ms:Math.max(0,deadline-Date.now()),evidence_timestamp:deadline-2200};
 await route.fulfill({contentType:'application/json',body:JSON.stringify(value)});
});
try{
 await page.goto((process.env.BJLAB_UI_URL||'http://127.0.0.1:8786')+'/?advisor=stream-1');
 await page.locator('.mini-action').filter({hasText:'HIT'}).waitFor();
 assert.match(await page.locator('.mini-hand').innerText(),/16[\s\S]*A = 1 \/ 11[\s\S]*6 or 16/);
 assert.equal(await page.locator('.mini-status').innerText(),'LIVE');
 assert.equal(await page.locator('.mini-count').innerText(),'R2 · COUNT UNVERIFIED');
 assert.equal(await page.locator('details,.probability-grid,.advisor-details,.advisor-count').count(),0);
 const geometry=await page.evaluate(()=>({width:document.documentElement.clientWidth,height:document.documentElement.clientHeight,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight}));
 assert.ok(geometry.scrollWidth<=geometry.width&&geometry.scrollHeight<=geometry.height,JSON.stringify(geometry));
 await page.screenshot({path:path.join(output,'compact-current.png')});
 checks.push('Compact 260 × 185 content fits without scrolling; soft ace, current action and separate unverified count');
 await page.getByRole('button',{name:'Always on top',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('[aria-label="Always on top"]')?.getAttribute('aria-pressed')==='false');
 await page.getByRole('button',{name:'Reset advisor position',exact:true}).click();
 await page.getByRole('button',{name:'Minimize advisor',exact:true}).click();
 await page.getByRole('button',{name:'Close advisor',exact:true}).click();
 assert.deepEqual(controls.map(control=>control.operation),['topmost','reset','minimize','hide']);
 assert.ok(controls.every(control=>control.stream_id==='stream-1'));
 checks.push('Pin/reset/minimize/hide controls retain selected observer identity; no observer creation route');
 deadline=Date.now()+250;
 await page.waitForFunction(()=>document.querySelector('.mini-status')?.textContent==='STALE');
 assert.equal(await page.locator('.mini-action').innerText(),'STALE');
 checks.push('Repeated polls cannot renew original evidence; expired action is withheld');
 deadline=Date.now()+2200;host.stream_id='stream-2';
 await page.waitForTimeout(500);
 assert.equal(await page.locator('.mini-action').innerText(),'STALE');
 checks.push('A selected-table mismatch cannot display a previous current action');
 host.stream_id='stream-1';
 await page.locator('.mini-action').filter({hasText:'HIT'}).waitFor();
 offline=true;
 await page.locator('.mini-error').waitFor();
 assert.equal(await page.locator('.mini-action').innerText(),'STALE');
 assert.equal(await page.locator('.mini-status').innerText(),'STALE');
 checks.push('Disconnected backend removes action despite previous valid report');
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'passed',scope:'isolated headless Chrome, mocked native state/control contracts; no vision or physical desktop acceptance',checks,geometry,errors},null,2)+'\n');
 console.log(JSON.stringify({status:'passed',checks,geometry,errors}));
}finally{await browser.close()}
