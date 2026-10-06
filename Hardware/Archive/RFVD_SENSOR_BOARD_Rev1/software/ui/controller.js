/* Workflow reference. No hardware acquisition or calibration activation. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.RFVDWorkflow = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const profiles = Object.freeze({raw_1m: 1000000, fir_500k: 500000, fir_250k: 250000});
  const busy = s => ['ARMED','RECORDING','SAVING'].includes(s.phase);
  const defaults = () => ({carrier:64, profile:'raw_1m', mode:'free', pulse:'Rectangular',
    test:'TF-001', dut:'AIMD-01', cable:'COAX-01', referencePlane:'Loaded AIMD terminal',
    preMs:100, postMs:1000, durationS:0, edge:'rising', thresholdCode:16000,
    hysteresisCode:1000, operator:'', notes:''});
  function validate(c) {
    const errors=[];
    if (![64,128].includes(c.carrier)) errors.push('Carrier must be 64 or 128 MHz.');
    if (!(c.profile in profiles)) errors.push('Unknown acquisition profile.');
    if (!['free','envelope','external'].includes(c.mode)) errors.push('Unknown capture mode.');
    for (const k of ['test','dut','cable','referencePlane']) if (typeof c[k]!=='string'||!c[k].trim()||c[k].length>80) errors.push(k+' must contain 1–80 characters.');
    for (const k of ['notes','operator','pulse']) if (typeof c[k]!=='string'||c[k].length>256) errors.push(k+' is invalid.');
    if (!Number.isInteger(c.preMs)||c.preMs<0||c.preMs>500) errors.push('Pretrigger must be 0–500 ms.');
    if (!Number.isInteger(c.postMs)||c.postMs<1||c.postMs>3600000) errors.push('Posttrigger must be 1–3600000 ms.');
    if (!Number.isFinite(c.durationS)||c.durationS<0||c.durationS>86400) errors.push('Duration must be 0–86400 s (0 = manual).');
    if (!['rising','falling'].includes(c.edge)) errors.push('Invalid trigger edge.');
    if (!Number.isInteger(c.thresholdCode)||c.thresholdCode<1||c.thresholdCode>65534) errors.push('Threshold must be 1–65534 raw ADC codes.');
    if (!Number.isInteger(c.hysteresisCode)||c.hysteresisCode<1||c.hysteresisCode>Math.min(c.thresholdCode,65535-c.thresholdCode)) errors.push('Hysteresis exceeds raw-code range.');
    return errors;
  }
  function create() { return {phase:'IDLE', config:defaults(), session:null, card:true, full:false,
    elapsedUs:0, acquiredPairs:0, markers:[], gaps:[], envelopeReady:false, fault:null, pretriggerPairs:0}; }
  function configure(s, patch) {
    if (busy(s)) throw Error('Stop and close the recording before changing settings.');
    for (const k of Object.keys(patch)) if (!(k in s.config)) throw Error('Unknown setting: '+k);
    const next={...s.config,...patch}, errors=validate(next);
    if (errors.length) throw Error(errors.join(' '));
    s.config=next; if(s.card&&!s.full)s.phase='IDLE';
  }
  function start(s) {
    if (busy(s)) throw Error('A recording is already active or closing.');
    if (!s.card||s.full||s.fault) throw Error('Insert a writable card and clear the fault before recording.');
    const errors=validate(s.config); if(errors.length)throw Error(errors.join(' '));
    s.session=Object.freeze({...s.config, nativeRate:1000000, outputRate:profiles[s.config.profile],
      calibrationId:null, sampleClock:'synthetic-workflow-clock', hardwareQualified:false});
    s.elapsedUs=0; s.acquiredPairs=0; s.pretriggerPairs=0; s.markers=[]; s.gaps=[];
    s.envelopeReady=false; s.triggerAtUs=null; s.phase=s.config.mode==='free'?'RECORDING':'ARMED';
  }
  function stop(s) {if (!['ARMED','RECORDING'].includes(s.phase))return false;s.phase='SAVING';return true;}
  function close(s, ok=true) {if(s.phase!=='SAVING')return false;if(!ok||!s.card){fail(s,'File close failed; recovery required.');return false;}s.phase='SAFE';return true;}
  function fail(s, reason) {s.phase='FAULT';s.fault=reason;}
  function card(s, present, full=false) {
    s.card=!!present; s.full=!!full;
    if ((!present||full)&&busy(s)) fail(s,present?'Card full; incomplete recording requires recovery.':'Card removed during acquisition or saving; recovery required.');
    else if(!present)s.phase=s.fault?'FAULT':'NO_CARD';
    else if(!busy(s)&&!s.fault)s.phase=full?'FULL':'IDLE';
  }
  function clearFault(s) {if(busy(s))throw Error('Cannot clear an active recording.');s.fault=null;s.phase=!s.card?'NO_CARD':s.full?'FULL':'IDLE';}
  function mark(s, kind='user') {if(!['ARMED','RECORDING'].includes(s.phase))return false;s.markers.push({kind,nativePairIndex:s.acquiredPairs});return true;}
  function trigger(s, kind, edge='rising') {
    if (kind==='external'&&['ARMED','RECORDING'].includes(s.phase)&&edge===s.session.edge)mark(s,'external');
    if(s.phase!=='ARMED'||kind!==s.session.mode||(kind==='external'&&edge!==s.session.edge))return false;
    s.pretriggerPairs=Math.min(s.acquiredPairs,s.session.preMs*1000);
    s.triggerAtUs=s.elapsedUs; s.phase='RECORDING';
    s.markers.push({kind:'accepted_'+kind,nativePairIndex:s.acquiredPairs,retainedPretriggerPairs:s.pretriggerPairs});return true;
  }
  function envelope(s, code) {
    if(s.phase!=='ARMED'||s.session.mode!=='envelope'||!Number.isInteger(code)||code<0||code>65535)return false;
    const c=s.session;
    if(c.edge==='rising') {if(code<=c.thresholdCode-c.hysteresisCode)s.envelopeReady=true;if(s.envelopeReady&&code>=c.thresholdCode)return trigger(s,'envelope');}
    else {if(code>=c.thresholdCode+c.hysteresisCode)s.envelopeReady=true;if(s.envelopeReady&&code<=c.thresholdCode)return trigger(s,'envelope');}
    return false;
  }
  function advance(s, us) {
    if(!Number.isSafeInteger(us)||us<0)throw Error('Time advance must be nonnegative integer microseconds.');
    if(!['ARMED','RECORDING'].includes(s.phase))return;
    let step=us;
    const limit=s.phase==='RECORDING'?(s.session.mode==='free'?(s.session.durationS?Math.round(s.session.durationS*1e6):Infinity):s.triggerAtUs+s.session.postMs*1000):Infinity;
    step=Math.min(step,Math.max(0,limit-s.elapsedUs));s.elapsedUs+=step;s.acquiredPairs+=step;
    if(s.elapsedUs>=limit)stop(s);
  }
  function gap(s, count) {
    if(s.phase!=='RECORDING'||!Number.isSafeInteger(count)||count<=0)throw Error('Gap requires recording and a positive native-pair count.');
    const first=s.acquiredPairs;advance(s,count);
    s.gaps.push({firstNativePair:first,missingNativePairs:s.acquiredPairs-first});
  }
  function estimate(c) {
    const rate=profiles[c.profile]||0, bytesPerSecond=rate*4;
    return {payloadBytesPerSecond:bytesPerSecond,pretriggerRawBytes:c.preMs*4000,
      // Reserve 2MiB for pretrigger and 4MiB for storage when triggered.
      storageReserveBytes:c.mode==='free'?6*1024*1024:4*1024*1024,
      payloadOnlyStallSeconds:(c.mode==='free'?6:4)*1024*1024/bytesPerSecond};
  }
  return {profiles,defaults,create,validate,configure,start,stop,close,fail,card,clearFault,mark,trigger,envelope,advance,gap,estimate,busy};
});
