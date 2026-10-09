import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadSource} from './load-ts.mjs';
const {captureGeometry,cropLayout,previewPoint,sourceDetectionBox}=await loadSource('capture-geometry.ts');
test('native table capture preserves original useful pixels while full 4K is capped',()=>{
 const full=captureGeometry(3840,2160,[0,0,1,1],null);assert.ok(full.scale<1);
 const region=captureGeometry(3840,2160,[.25,.25,.25,.5],null);assert.deepEqual(region.source_rect,[960,540,960,1080]);assert.deepEqual(region.upload_size,[960,1080]);assert.equal(region.native,true);
});
test('preview coordinates exclude letterbox bands and are invariant to CSS/DPI scale',()=>{
 assert.equal(previewPoint(0,0,{left:0,top:0,width:100,height:100},200,100),null);
 assert.deepEqual(previewPoint(50,50,{left:0,top:0,width:100,height:100},200,100),[.5,.5]);
 assert.deepEqual(previewPoint(200,200,{left:100,top:100,width:200,height:200},200,100),[.5,.5]);
});
test('source regions map into uploaded crop without changing their meaning',()=>{
 const layout={table:[.25,.25,.5,.5],dealer:[.4,.3,.2,.1], 'player:0':[.4,.6,.2,.1]};
 const mapped=cropLayout(layout,2000,1000);assert.deepEqual(mapped.table,[0,0,1,1]);
 assert.deepEqual(mapped.dealer,[.3,.1,.4,.2]);assert.deepEqual(mapped['player:0'],[.3,.7,.4,.2]);
});
test('invalid crop bounds cannot silently select another area',()=>{
 assert.throws(()=>captureGeometry(100,100,[.9,0,.2,1]),/valid region/);
});
test('overlay detections map out of a native or scaled crop into the full preview',()=>{
 assert.deepEqual(sourceDetectionBox([10,20,30,40],{source_rect:[500,200,800,600],upload_size:[400,300]}),[520,240,60,80]);
});
