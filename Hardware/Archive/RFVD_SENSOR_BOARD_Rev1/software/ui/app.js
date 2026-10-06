'use strict';
const W=RFVDWorkflow, s=W.create(), $=id=>document.getElementById(id);
const names={raw_1m:'Raw 1 Mpair/s',fir_500k:'FIR 500 kpair/s',fir_250k:'FIR 250 kpair/s'},modes={free:'Free run',envelope:'Envelope trigger',external:'External trigger'};
let tab='Setup',page=0,calstep=0,calref='',closeTimer=null,logs=[],wave=0;
function html(x){return String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function log(x){logs.push(new Date().toLocaleTimeString()+'  '+x);$('log').textContent=logs.slice(-12).join('\n');}
function run(fn){try{fn();}catch(e){log(e.message);}render();scheduleClose();}
function options(values,current){return Object.entries(values).map(([v,label])=>`<option value="${v}" ${v===String(current)?'selected':''}>${html(label)}</option>`).join('');}
function field(k,label,type='number',min='',max=''){return `<label><span class="label">${label}</span><input class="field" data-key="${k}" type="${type}" ${min!==''?`min="${min}"`:''} ${max!==''?`max="${max}"`:''} value="${html(s.config[k])}"></label>`;}
function select(k,label,values){return `<label><span class="label">${label}</span><select class="field" data-key="${k}">${options(values,s.config[k])}</select></label>`;}
function render(){
 const c=s.config,active=W.busy(s), e=W.estimate(c);
 $('topstate').textContent=s.phase==='SAFE'?'SAFE TO REMOVE':s.phase;
 $('topmeta').textContent=c.carrier+' MHz · '+(s.card?(s.full?'SD FULL':'SD demo'):'NO CARD')+' · RAW CODES';
 $('tabs').innerHTML=['Setup','Record','Calibrate','Service'].map(t=>`<button class="${tab===t?'active':''}" data-tab="${t}">${t}</button>`).join('');
 let h='';
 if(tab==='Setup'){
  h=`<div class="stats"><b>Test configuration ${page+1}/3</b><button class="smallbtn" id="next">Next ›</button></div>`;
  if(page===0)h+=`<div class="grid">${select('carrier','Carrier / calibration band',{64:'64 MHz',128:'128 MHz'})}${select('profile','Saved data',names)}${select('pulse','Pulse description',{Rectangular:'Rectangular',Gaussian:'Gaussian',Sinc:'Sinc',Custom:'Custom'})}${select('mode','Capture behavior',modes)}</div><div class="row"><input class="field" style="width:185px" aria-label="Test ID" data-key="test" value="${html(c.test)}"><button class="primary" id="start">${c.mode==='free'?'Record':'Arm'}</button></div><div class="muted">${(e.payloadBytesPerSecond/1e6).toFixed(1)} MB/s payload · <span class="warn">UNCALIBRATED</span></div>`;
  if(page===1)h+=`<div class="grid">${field('preMs','Pretrigger ms · 0–500','number',0,500)}${field('postMs','Posttrigger ms','number',1,3600000)}${field('thresholdCode','Threshold · raw VENV code','number',1,65534)}${field('hysteresisCode','Hysteresis · codes','number',1,32767)}${select('edge','Trigger edge',{rising:'Rising',falling:'Falling'})}${field('durationS','Free-run seconds · 0=manual','number',0,86400)}</div><p class="muted">Trigger levels use raw VENV codes until calibration is validated.</p>`;
  if(page===2)h+=`<div class="grid">${field('dut','DUT ID','text')}${field('cable','Cable / fixture ID','text')}${field('operator','Operator','text')}${field('referencePlane','Voltage reference plane','text')}</div><div class="row">${field('notes','Experiment notes','text')}</div><p class="muted">Settings freeze when armed. Carrier selection labels<br>the experiment; it does not tune the broadband input.</p>`;
 }
 if(tab==='Record')h=`<div class="stats"><b>${html(s.session?.test||c.test)}</b><span class="pill">${s.phase}</span></div><canvas id="plot" width="596" height="166" aria-label="Synthetic raw-code envelope plot"></canvas><div class="stats"><span id="elapsed">${(s.elapsedUs/1e6).toFixed(2)} s</span><span>${s.markers.length} events</span><span class="${s.gaps.length?'warn':''}">${s.gaps.length} gaps</span></div><div class="muted">${html(names[s.session?.profile||c.profile])} · synthetic codes</div><div class="row"><button class="primary ${active?'danger':''}" id="start">${s.phase==='SAVING'?'Saving…':active?'Stop & save':c.mode==='free'?'Record':'Arm'}</button><button class="chip" id="mark">Mark</button></div><div class="muted">${s.fault?'Recording interrupted — recover incomplete files.':s.phase==='SAFE'?'File close acknowledged — safe to remove SD':s.phase==='ARMED'?'Pretrigger history is rolling; waiting for event':'UNCALIBRATED · no validated volts'}</div>`;
 if(tab==='Calibrate'){
  h=`<h2>Calibration · ${c.carrier} MHz</h2><span class="label">STEP ${calstep+1} OF 3</span>`;
  if(calstep===0)h+=`<input class="field" id="calref" placeholder="Reference instrument ID" value="${html(calref)}"><p class="muted">Use the installed cable and declared reference plane.<br>Record reference uncertainty and board temperature.<br>Fit and validation runs must be independent.</p><button class="primary" id="calnext">Continue</button>`;
  if(calstep===1)h+=`<table><tr><td>Reference</td><td>${html(calref)}</td></tr><tr><td>Cable</td><td>${html(c.cable)}</td></tr><tr><td>Observations</td><td>None — demo only</td></tr></table><p class="muted">Collect real readings from the reference instrument<br>and retain the matching raw captures.</p><button class="smallbtn" id="calnext">Review requirements</button>`;
  if(calstep===2)h+=`<p class="warn">Activation blocked: no measurement evidence.</p><p class="muted">Required: matching board/cable/carrier, independent<br>validation, voltage range, temperature range,<br>uncertainty and immutable coefficient identity.<br>The display must never relabel raw codes as volts.</p><button class="smallbtn" id="calreset">Restart wizard</button>`;
 }
 if(tab==='Service')h=`<h2>Uncalibrated service</h2><table><tr><td>ADC / rails / temperature</td><td>Hardware absent</td></tr><tr><td>PSRAM / SD latency</td><td>Not measured</td></tr><tr><td>Card state</td><td>${!s.card?'Absent':s.full?'Full':'Demo writable'}</td></tr><tr><td>Calibration / qualification</td><td>Not activated</td></tr></table><div class="row"><button class="smallbtn" id="clear">Acknowledge fault</button></div><p class="muted">SWD J3 / UART J5. Primary recovery uses SWD.<br>ROM recovery requires documented isolation steps.</p>`;
 $('content').innerHTML=h;
 document.querySelectorAll('[data-tab]').forEach(x=>x.onclick=()=>{tab=x.dataset.tab;render();});
 document.querySelectorAll('[data-key]').forEach(x=>{x.disabled=active;x.onchange=()=>run(()=>W.configure(s,{[x.dataset.key]:x.type==='number'||x.dataset.key==='carrier'?Number(x.value):x.value}));});
 if($('next'))$('next').onclick=()=>{page=(page+1)%3;render();};
 if($('start')){$('start').onclick=startStop;$('start').disabled=s.phase==='SAVING'||s.phase==='FAULT'||!s.card||s.full;}
 if($('mark'))$('mark').onclick=()=>run(()=>{if(W.mark(s))log('User marker at native index '+s.acquiredPairs);});
 if($('calref')){$('calref').disabled=active;$('calref').onchange=x=>calref=x.target.value;}
 if($('calnext')){$('calnext').disabled=active;$('calnext').onclick=()=>run(()=>{if(!calref.trim())throw Error('Enter reference instrument ID.');calstep++;});}
 if($('calreset')){$('calreset').disabled=active;$('calreset').onclick=()=>{calstep=0;render();};}
 if($('clear')){$('clear').disabled=active;$('clear').onclick=()=>run(()=>{W.clearFault(s);log('Fault acknowledged. Recover incomplete files before using that card.');});}
 draw();
}
function startStop(){run(()=>{if(W.busy(s)){if(W.stop(s))log('Draining and closing demo file.');}else{W.start(s);log(s.phase==='ARMED'?'Armed with immutable settings.':'Recording autonomously; no external trigger required.');}tab='Record';});}
function scheduleClose(){if(s.phase==='SAVING'&&!closeTimer)closeTimer=setTimeout(()=>{closeTimer=null;if(W.close(s))log('Simulated file close acknowledged. Safe to remove card.');render();},550);}
function draw(){const c=$('plot');if(!c)return;const ctx=c.getContext('2d');ctx.fillStyle='#0d2530';ctx.fillRect(0,0,596,166);ctx.strokeStyle='#234551';for(let y=35;y<166;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(596,y);ctx.stroke();}ctx.strokeStyle='#72e2c2';ctx.lineWidth=2;ctx.beginPath();for(let i=0;i<596;i++){const t=(i-280)/70,v=s.config.pulse==='Gaussian'?Math.exp(-t*t):s.config.pulse==='Sinc'?Math.abs(t===0?1:Math.sin(3*t)/(3*t)):1/(1+Math.exp(-(i-180)/4))/(1+Math.exp((i-380)/4));ctx.lineTo(i,140-v*(85+20*wave));}ctx.stroke();ctx.fillStyle='#84acb9';ctx.font='16px system-ui';ctx.fillText('Synthetic VENV raw codes',12,22);if(s.gaps.length){ctx.fillStyle='#ffaf9390';ctx.fillRect(440,0,22,166);}}
$('recordPhysical').onclick=startStop;$('markPhysical').onclick=()=>run(()=>W.mark(s));
$('pulse').onclick=()=>run(()=>{wave=1;const c=s.session||s.config;W.envelope(s,c.edge==='rising'?0:65535);const accepted=W.envelope(s,c.thresholdCode);log(accepted?'Envelope threshold accepted.':'Synthetic RF pulse; capture state unchanged.');});
$('trigger').onclick=()=>run(()=>{const accepted=W.trigger(s,'external',(s.session||s.config).edge);log(accepted?'External trigger accepted.':'External event simulated.');});
$('stall').onclick=()=>run(()=>{W.gap(s,20000);log('Simulated overflow: exact native-pair gap retained.');});
$('cardToggle').onclick=()=>run(()=>{W.card(s,!s.card,false);log(s.card?'Demo card inserted.':'Demo card removed.');});
$('cardFull').onclick=()=>run(()=>{W.card(s,true,true);log('Demo card full.');});
$('export').onclick=()=>{const data={artifact:'synthetic-ui-demo-not-an-experiment',phase:s.phase,configuration:s.config,session:s.session,markers:s.markers,gaps:s.gaps,events:logs,calibrationActivated:false};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download='rfvd-demo-metadata.json';a.click();URL.revokeObjectURL(a.href);};
setInterval(()=>{const before=s.phase;W.advance(s,100000);wave*=.9;if(s.phase!==before)render();else{if($('elapsed'))$('elapsed').textContent=(s.elapsedUs/1e6).toFixed(2)+' s';draw();}scheduleClose();},100);
log('Workflow reference: synthetic raw codes; no hardware or calibration claim.');render();
