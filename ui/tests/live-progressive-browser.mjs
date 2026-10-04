/** Actual isolated Chromium UI; no remote sites, private images or installs. */
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),pw=require(process.argv[2]);
const root=path.resolve(import.meta.dirname,'../..');
const browser=await pw.chromium.launch({headless:true,channel:'chrome'});
const context=await browser.newContext({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
await context.addInitScript(()=>{localStorage.setItem('bjlab.language','en');localStorage.setItem('bjlab.reuseRules','yes')});
const page=await context.newPage(),errors=[],frames=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('response',async response=>{if(response.url().includes('/frame?')&&response.request().method()==='POST'&&response.status()===200){try{frames.push(await response.json())}catch{}}});
const output=path.join(root,'experiments/live_reliability/browser.json');
const results={version:'1.1.1',scope:'headless Chrome, owned lab canvas video and real local REST service; no personal display picker or external provider footage',checks,errors};
try{
 await page.goto(process.env.BJLAB_URL||'http://127.0.0.1:8768');
 assert.match(await page.locator('.sidebar .version').innerText(),/1\.1\.1/);
 checks.push('Visible application version matches the package and backend version');
 await page.getByRole('button',{name:'Live vision',exact:true}).click();
 const table=page.locator('.table-workspace').first();
 await table.getByRole('button',{name:'Run lab demo',exact:true}).click();
 await table.getByRole('button',{name:'Pause bot',exact:true}).click();
 const deal=table.getByRole('button',{name:'Deal',exact:true});if(await deal.isVisible())await deal.click();
 await table.locator('.action-title').filter({hasText:/^(Hit|Stand|Double|Split|Surrender)$/}).waitFor({timeout:15000});
 assert.ok(frames.some(r=>r.advice&&r.decision===null&&r.advice.basis==='basic-strategy'));
 checks.push('Actual video UI displays basic policy from a frame response without Monte Carlo');
 await table.locator('.probability-grid strong').first().filter({hasText:/%/}).waitFor({timeout:10000});
 checks.push('Independent analysis polling supplies probabilities for the same state');
 const stable=frames.findLast(r=>r.advice);results.initial={player:stable.player,dealer:stable.dealer,action:stable.advice.best_action,count_history:stable.count_history,state_id:stable.state_id};
 await table.getByRole('button',{name:'Open advisor',exact:true}).click();
 assert.ok(await page.getByRole('complementary',{name:'In-page advisor fallback'}).isVisible());
 assert.match(await page.getByRole('complementary',{name:'In-page advisor fallback'}).innerText(),/cannot move outside this app/);
 checks.push('Unavailable native/PiP host is explicitly labelled as in-page fallback');
 await page.getByRole('complementary',{name:'In-page advisor fallback'}).getByRole('button',{name:'Close advisor',exact:true}).click();
 await table.getByRole('button',{name:'Stop video',exact:true}).click();
 // Exercise the real API contract for a mid-shoe start without changing pixels.
 await page.route('**/api/live',async route=>{
  if(route.request().method()==='POST'){const body=route.request().postDataJSON();body.fresh_shoe=false;await route.continue({postData:JSON.stringify(body)})}else await route.continue();
 });
 frames.length=0;
 await table.getByRole('button',{name:'Run lab demo',exact:true}).click();
 await table.getByRole('button',{name:'Pause bot',exact:true}).click();
 if(await deal.isVisible())await deal.click();
 await table.locator('.action-title').filter({hasText:/^(Hit|Stand|Double|Split|Surrender)$/}).waitFor({timeout:15000});
 await table.locator('.gate-note').filter({hasText:/mid-shoe/}).waitFor();
 const partial=frames.findLast(r=>r.advice);assert.equal(partial.true_count,null);assert.equal(partial.physical_remaining,null);assert.equal(partial.count_history,'partial');
 checks.push('Mid-shoe live video retains a base action and displays unknown TC/inventory');
 await table.getByRole('button',{name:'Stop video',exact:true}).click();
 await page.unroute('**/api/live');
 for(let index=0;index<4;index++)await page.getByRole('button',{name:'+ Add table',exact:true}).click();
 assert.equal(await page.locator('.table-workspace').count(),5);
 frames.length=0;
 for(let index=0;index<5;index++){
  const area=page.locator('.table-workspace').nth(index);
  await area.getByRole('button',{name:'Run lab demo',exact:true}).click();
  await area.getByRole('button',{name:'Pause bot',exact:true}).click();
  const next=area.getByRole('button',{name:'Deal',exact:true});if(await next.isVisible())await next.click();
 }
 await page.waitForFunction(()=>document.querySelectorAll('.table-workspace .action-title').length===5&&[...document.querySelectorAll('.table-workspace .action-title')].every(x=>/^(Hit|Stand|Double|Split|Surrender)$/.test(x.textContent||'')),{},{timeout:25000});
 results.five_tables=await page.locator('.table-workspace').evaluateAll(areas=>areas.map(area=>({action:area.querySelector('.action-title')?.textContent,cards:area.querySelector('.advisor-cards')?.textContent,metrics:area.querySelector('.live-metrics')?.textContent})));
 assert.equal(new Set(frames.filter(r=>r.advice).map(r=>r.state_id?.split(':')[0])).size,5);
 checks.push('Five concurrent owned video sources keep separate identities and legal basic advice');
 assert.deepEqual(errors,[]);results.status='passed';
 for(let index=0;index<5;index++)await page.locator('.table-workspace').nth(index).getByRole('button',{name:'Stop video',exact:true}).click();
}catch(error){results.status='failed';results.failure=String(error);throw error}
finally{fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(results,null,2)+'\n');await browser.close();console.log(JSON.stringify(results))}
