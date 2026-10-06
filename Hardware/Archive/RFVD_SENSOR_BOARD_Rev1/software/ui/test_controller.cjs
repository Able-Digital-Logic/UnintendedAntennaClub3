const test=require('node:test'),assert=require('node:assert/strict'),W=require('./controller.js');
test('capture configuration is immutable through arm, capture and saving',()=>{
 const s=W.create();W.configure(s,{mode:'external',profile:'fir_250k'});W.start(s);
 assert.throws(()=>W.configure(s,{carrier:128}));s.config.carrier=128;assert.equal(s.session.carrier,64);
 W.trigger(s,'external');assert.throws(()=>W.start(s));W.stop(s);assert.throws(()=>W.configure(s,{test:'changed'}));
 W.close(s);assert.equal(s.phase,'SAFE');W.configure(s,{test:'next'});assert.equal(s.phase,'IDLE');
});
test('native index and partial prehistory are preserved for every output profile',()=>{
 for(const profile of Object.keys(W.profiles)){const s=W.create();W.configure(s,{mode:'external',profile,preMs:100,postMs:1});W.start(s);W.advance(s,12345);W.trigger(s,'external');assert.equal(s.pretriggerPairs,12345);W.advance(s,5000);assert.equal(s.acquiredPairs,13345);assert.equal(s.phase,'SAVING');}
});
test('wrong edge and wrong source cannot start a triggered record',()=>{
 const s=W.create();W.configure(s,{mode:'external',edge:'falling'});W.start(s);assert.equal(W.trigger(s,'external','rising'),false);assert.equal(W.trigger(s,'envelope'),false);assert.equal(s.phase,'ARMED');assert.equal(W.trigger(s,'external','falling'),true);
});
test('envelope hysteresis requires arming on the opposite side',()=>{
 for(const edge of ['rising','falling']){const s=W.create();W.configure(s,{mode:'envelope',edge,thresholdCode:10000,hysteresisCode:100});W.start(s);assert.equal(W.envelope(s,10000),false);assert.equal(W.envelope(s,edge==='rising'?9950:10050),false);W.envelope(s,edge==='rising'?9900:10100);assert.equal(W.envelope(s,10000),true);}
});
test('card removal during arm, recording or closing cannot claim safe remove',()=>{
 for(const phase of ['ARMED','RECORDING','SAVING']){const s=W.create();W.configure(s,{mode:phase==='ARMED'?'external':'free'});W.start(s);if(phase==='SAVING')W.stop(s);W.card(s,false);assert.equal(s.phase,'FAULT');assert.equal(W.close(s),false);W.card(s,true);assert.throws(()=>W.start(s));W.clearFault(s);W.start(s);}
});
test('card full and unsuccessful close require recovery acknowledgement',()=>{
 const s=W.create();W.card(s,true,true);assert.throws(()=>W.start(s));W.card(s,true,false);W.start(s);W.stop(s);assert.equal(W.close(s,false),false);assert.equal(s.phase,'FAULT');
});
test('free run needs no trigger and stops on precise duration boundary',()=>{
 const s=W.create();W.configure(s,{durationS:.125});W.start(s);W.advance(s,200000);assert.equal(s.phase,'SAVING');assert.equal(s.acquiredPairs,125000);W.close(s);assert.equal(s.phase,'SAFE');
});
test('gaps identify exact missing native sample interval',()=>{
 const s=W.create();W.start(s);W.advance(s,123);W.gap(s,4000);assert.deepEqual(s.gaps,[{firstNativePair:123,missingNativePairs:4000}]);assert.equal(s.acquiredPairs,4123);assert.throws(()=>W.gap(s,-1));
});
test('invalid settings fail before configuration changes',()=>{
 const s=W.create();for(const patch of [{preMs:501},{thresholdCode:65535},{hysteresisCode:50000},{profile:'mystery'},{durationS:NaN},{test:''},{unknown:1}])assert.throws(()=>W.configure(s,patch));assert.equal(s.config.preMs,100);
});
test('gap at timed stop is bounded by the actual recording interval',()=>{
 const s=W.create();W.configure(s,{durationS:.001});W.start(s);W.advance(s,990);W.gap(s,100);assert.deepEqual(s.gaps,[{firstNativePair:990,missingNativePairs:10}]);assert.equal(s.phase,'SAVING');
});
test('maximum raw prehistory stays within 2MiB allocation',()=>{
 const e=W.estimate({...W.defaults(),mode:'external',preMs:500});assert.ok(e.pretriggerRawBytes<2*1024*1024);assert.equal(e.storageReserveBytes,4*1024*1024);
});
