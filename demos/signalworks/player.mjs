export function validateTraces(data) {
  const invalid=()=>{throw Error('Invalid recorded trace data');};
  const text=v=>typeof v==='string'&&v.length>0;
  const integer=v=>Number.isSafeInteger(v)&&v>=0;
  const outcomes=new Set(['ready','applied','replayed','quarantined','rolled_back','blocked','stale']);
  if(data?.schema_version!==1||!Array.isArray(data.scenarios)||!data.scenarios.length)invalid();
  const ids=new Set();
  for(const scenario of data.scenarios){
    if(!text(scenario.id)||ids.has(scenario.id)||!text(scenario.title)||!text(scenario.description)||!Array.isArray(scenario.steps)||!scenario.steps.length)invalid();
    ids.add(scenario.id);
    for(const step of scenario.steps){
      if(!step||!outcomes.has(step.disposition)||!text(step.explanation)||typeof step.transport_fixture!=='boolean')invalid();
      if(step.disposition==='ready'){
        if(step.event_id!==null||step.sequence!==null||step.version!==null)invalid();
      }else if(!text(step.event_id)||!integer(step.sequence)||step.sequence<1||!integer(step.version)||step.version<1)invalid();
      const state=step.state;
      if(!state||!['checkpoint','active_orders','quarantine_count','receipt_count','paid_cents','tombstones'].every(k=>integer(state[k]))||!Array.isArray(state.entities))invalid();
      for(const entity of state.entities)if(!text(entity.key)||!integer(entity.version)||entity.version<1||typeof entity.deleted!=='boolean')invalid();
    }
  }
  return data;
}

export function createPlayer(traces, onChange, {schedule = fn => setTimeout(fn, 1700), cancel = clearTimeout} = {}) {
  if (!traces?.scenarios?.length || traces.scenarios.some(s=>!s.id || !s.steps?.length)) throw Error('No recorded scenarios available');
  let scenario=traces.scenarios[0], index=0, playing=false, timer=null, generation=0, destroyed=false;
  const state=()=>({scenario,index,playing,step:scenario.steps[index]});
  const notify=()=>onChange(state());
  const check=()=>{if(destroyed)throw Error('Player destroyed');};
  function pause(){generation++;if(timer!==null)cancel(timer);timer=null;playing=false;notify();}
  function tick(token){if(token!==generation||!playing||destroyed)return;index=Math.min(index+1,scenario.steps.length-1);if(index===scenario.steps.length-1)playing=false;notify();if(playing)timer=schedule(()=>tick(token));}
  const api={get state(){return state();},
    select(id){check();const next=traces.scenarios.find(s=>s.id===id);if(!next)throw Error('Unknown scenario');pause();scenario=next;index=0;notify();},
    step(){check();pause();index=Math.min(index+1,scenario.steps.length-1);notify();},
    play(){check();pause();if(index===scenario.steps.length-1)index=0;playing=true;notify();const token=generation;timer=schedule(()=>tick(token));},
    pause,
    reset(){check();pause();index=0;notify();},
    destroy(){pause();destroyed=true;}
  };
  notify();return api;
}
