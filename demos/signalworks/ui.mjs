import {createPlayer,validateTraces} from './player.mjs';
import {machine} from './geometry.mjs';
const $=id=>document.getElementById(id);
const controls=[...document.querySelectorAll('.presets button'),$('scenario'),$('play'),$('step'),$('reset')];
let player, animation=0, previousStep=null;
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const stage=document.querySelector('.iso-stage svg');
function draw(state){
  cancelAnimationFrame(animation);
  const {scenario,index,step,playing}=state;
  const changed=previousStep!==step;previousStep=step;
  $('scenario').value=scenario.id;
  document.querySelectorAll('[data-scenario]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.scenario===scenario.id)));
  for(const key of ['checkpoint','active_orders','quarantine_count','receipt_count','paid_cents'])$(''+key).textContent=key==='paid_cents'?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(step.state[key]/100):String(step.state[key]);
  $('outcome').textContent=step.disposition.replaceAll('_',' ').toUpperCase()+(step.disposition==='ready'?' / UNCOMMITTED':'');
  $('scenario-title').textContent=scenario.title;
  $('explanation').textContent=step.explanation;
  $('event-meta').textContent=step.event_id?`SEQUENCE ${step.sequence} / ENTITY VERSION ${step.version}${step.transport_fixture?' / TRANSPORT FIXTURE':''}`:'DURABLE OUTBOX / WAITING FOR CONSUMPTION';
  $('progress').textContent=`Step ${index+1} / ${scenario.steps.length} · ${playing?'Playing':'Paused'}`;
  $('play').textContent=playing?'Pause Ⅱ':'Run experiment ▶';
  $('step').disabled=index===scenario.steps.length-1;
  $('history').replaceChildren(...scenario.steps.slice(0,index+1).map((s,i)=>{const li=document.createElement('li');li.textContent=`${i+1}. ${s.disposition.replaceAll('_',' ')} — ${s.explanation} Checkpoint ${s.state.checkpoint}; paid cents ${s.state.paid_cents}.`;return li;}));
  // Geometry is trusted local code; no trace text enters SVG markup.
  stage.innerHTML=machine(step.disposition);
  if(changed && !reduced.matches && step.disposition!=='ready'){
    let start;
    const frame=now=>{start??=now;const t=Math.min(1,(now-start)/650);stage.innerHTML=machine(step.disposition,1-(1-t)**3);if(t<1)animation=requestAnimationFrame(frame);};
    animation=requestAnimationFrame(frame);
  }
}
$('theme').addEventListener('click',()=>{const light=document.documentElement.dataset.theme!=='light';document.documentElement.dataset.theme=light?'light':'dark';document.querySelector('.machine-card').dataset.theme=light?'light':'dark';$('theme').textContent=light?'Dark theme':'Light theme';});
async function initialize(){
  try{
    const response=await fetch('./traces.json');if(!response.ok)throw Error(`Trace load failed (${response.status})`);
    const traces=validateTraces(await response.json());
    $('scenario').replaceChildren(...traces.scenarios.map(s=>{const o=document.createElement('option');o.value=s.id;o.textContent=s.title;return o;}));
    controls.forEach(c=>c.disabled=false);
    player=createPlayer(traces,draw);
    $('scenario').addEventListener('change',e=>player.select(e.target.value));
    document.querySelectorAll('[data-scenario]').forEach(b=>b.addEventListener('click',()=>player.select(b.dataset.scenario)));
    $('play').addEventListener('click',()=>player.state.playing?player.pause():player.play());
    $('step').addEventListener('click',()=>player.step());$('reset').addEventListener('click',()=>player.reset());
    const observer=new IntersectionObserver(entries=>{if(!entries[0].isIntersecting){player.pause();cancelAnimationFrame(animation);}},{threshold:.05});observer.observe(document.querySelector('.machine-card'));
    document.addEventListener('visibilitychange',()=>{if(document.hidden){player.pause();cancelAnimationFrame(animation);}});
    reduced.addEventListener('change',()=>{player.pause();cancelAnimationFrame(animation);});
    window.addEventListener('pagehide',event=>{player.pause();cancelAnimationFrame(animation);if(!event.persisted){observer.disconnect();player.destroy();}});
  }catch(error){controls.forEach(c=>c.disabled=true);$('scenario-title').textContent='Recorded run unavailable';$('explanation').textContent='The recorded data could not be loaded. Read the case study or run the Python recorder locally. Serve this folder over HTTP rather than opening it as a file.';$('progress').textContent='Replay unavailable';console.warn(error.message);}
}
initialize();
