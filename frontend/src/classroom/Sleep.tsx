import React,{useEffect,useMemo,useRef,useState}from'react';
import{api}from'../api';
import{isPhysicallyInRoom}from'../presence';
import{ChildSelector}from'./ChildSelector';
import{EffectiveTime}from'./EffectiveTime';
import{Choice,stableEffective}from'./OrdinaryWorkflows';
import{WorkflowWorkspace}from'./WorkflowWorkspace';
import{operationId,type Child,type WorkflowProps}from'./types';

export type SleepSession={
  id:string;
  child_id:string;
  child_name:string;
  room_id:string;
  state:'settling'|'sleeping'|'awake_resting';
  status:'green'|'amber'|'red';
  last_check_at?:string|null;
  next_due_at?:string|null;
  put_down_at?:string|null;
  fell_asleep_at?:string|null;
  woke_at?:string|null;
  stale?:boolean;
  stale_reason?:string|null;
  check_interval_minutes:number
};

export const sleepCounts=(sessions:SleepSession[],roomId:string)=>({
  settling:sessions.filter(s=>s.room_id===roomId&&s.state==='settling').length,
  sleeping:sessions.filter(s=>s.room_id===roomId&&s.state==='sleeping').length,
  worst:sessions.some(s=>s.room_id===roomId&&s.status==='red')
    ?'red'
    :sessions.some(s=>s.room_id===roomId&&s.status==='amber')
      ?'amber'
      :'green'
});

export const sleepingChildIds=(sessions:SleepSession[],roomId:string)=>
  sessions
    .filter(s=>s.room_id===roomId&&s.state==='sleeping'&&!s.stale)
    .map(s=>s.child_id);

export function SleepWorkflow({
  check=false,
  initialAction,
  ...props
}:WorkflowProps&{
  check?:boolean;
  initialAction?:'put_down'|'fell_asleep'|'wake'|'got_up'
}){
  const[sessions,setSessions]=useState<SleepSession[]>([]);
  const[selected,setSelected]=useState<string[]>([]);
  const[action,setAction]=useState(
    check?'check':initialAction||'put_down'
  );
  const[time,setTime]=useState('');
  const[note,setNote]=useState('');
  const[warmth,setWarmth]=useState('normal');
  const[breathing,setBreathing]=useState('normal');
  const[wellbeing,setWellbeing]=useState('well');
  const[saving,setSaving]=useState(false);

  const op=useRef(operationId(check?'sleep-check':'sleep'));
  const implicit=useRef<string>();

  const load=()=>
    api('/classroom/sleep-status')
      .then(x=>setSessions(x.sessions));

  useEffect(()=>{
    void load();
  },[]);

  useEffect(()=>{
    setSelected([]);
  },[action]);

  const byChild=useMemo(
    ()=>Object.fromEntries(
      sessions.map(s=>[s.child_id,s])
    ),
    [sessions]
  );

  const roomNames=useMemo<Record<string,string>>(
    ()=>Object.fromEntries(
      props.data.rooms.map(r=>[r.id,r.name])
    ),
    [props.data.rooms]
  );

  const eligible=(child:Child)=>{
    const s:SleepSession|undefined=byChild[child.id];
    const sameRoom=!!s&&s.room_id===props.roomId;

    if(check){
      return !!s &&
        sameRoom &&
        !s.stale &&
        s.state==='sleeping';
    }

    if(action==='put_down'){
      return isPhysicallyInRoom(child,props.roomId)&&!s;
    }

    if(!s||!sameRoom){
      // A tired, physically present child can fall asleep without an
      // intermediate settling action. The server creates that session
      // atomically, so this remains safe for an offline/retry-prone tablet.
      return action==='fell_asleep' && !s && isPhysicallyInRoom(child,props.roomId);
    }

    if(s.stale){
      return action==='got_up';
    }

    if(action==='fell_asleep'){
      return s.state==='settling';
    }

    if(action==='wake'){
      return s.state==='sleeping';
    }

    if(action==='got_up'){
      return true;
    }

    return false;
  };

  const reason=(child:Child)=>{
    const s:SleepSession|undefined=byChild[child.id];

    if(s&&s.room_id!==props.roomId){
      return `Sleep active in ${roomNames[s.room_id]||'another room'}`;
    }

    if(s?.stale&&action!=='got_up'){
      return 'Previous sleep needs closing with Got up';
    }

    if(check){
      if(!s)return 'No active sleep session';
      return `Currently ${s.state.replace('_',' ')}`;
    }

    if(action==='put_down'){
      if(s)return `Already ${s.state.replace('_',' ')}`;

      return isPhysicallyInRoom(child,props.roomId)
        ?'Available'
        :'Not physically in this room';
    }

    if(!s){
      return action==='fell_asleep'&&isPhysicallyInRoom(child,props.roomId)
        ?'Available to record asleep immediately'
        :'No active sleep session';
    }

    return `Currently ${s.state.replace('_',' ')}`;
  };

  const state=(child:Child)=>{
    const s:SleepSession|undefined=byChild[child.id];

    if(!s){
      if(isPhysicallyInRoom(child,props.roomId)){
        return 'Available';
      }

      return child.present
        ?'Present elsewhere'
        :'Absent';
    }

    const room=
      s.room_id===props.roomId
        ?''
        :` · ${roomNames[s.room_id]||'other room'}`;

    return `${s.state.replace('_',' ')}${room}${s.stale?' · needs closing':''}`;
  };

  const save=async()=>{
    if(!selected.length||saving)return;

    setSaving(true);

    try{
      await api('/classroom/sleep',{
        method:'POST',
        body:JSON.stringify({
          client_id:op.current,
          child_ids:selected,
          room_id:props.roomId,
          action,
          effective_at:stableEffective(implicit,time),
          staff_id:props.staffId,
          warmth,
          breathing,
          wellbeing,
          note:note||undefined
        })
      });

      const message=
        check
          ?'Sleep check recorded'
          :`Sleep action recorded: ${action.replace('_',' ')}`;

      // The POST succeeded. Never let a subsequent screen-refresh
      // failure invite the teacher to submit the care action again.
      props.notice(message);
      props.close();

      void props.refresh().catch(()=>
        props.notice(
          `${message} — screen refresh failed; reopen to refresh`
        )
      );
    }catch(e:any){
      setSaving(false);
      props.notice(e.message);
    }
  };

  const sleeping=sessions.filter(
    s=>
      s.room_id===props.roomId &&
      s.state==='sleeping' &&
      !s.stale
  );

  return(
    <WorkflowWorkspace
      title={check?'Sleep Check':'Sleep'}
      close={props.close}
      roster={
        <ChildSelector
          children={props.data.children}
          rooms={props.data.rooms}
          roomId={props.roomId}
          selected={selected}
          setSelected={setSelected}
          filter={eligible}
          eligibilityLabel={reason}
          stateLabel={state}
          recentVisitorIds={props.data.recent_visitors?.[props.roomId]}
          bulkLabel={
            check
              ?'Select all sleeping'
              :'Select all eligible present'
          }
        />
      }
      footer={
        <button
          className="save"
          disabled={!selected.length||saving}
          onClick={save}
        >
          {saving
            ?'Saving…'
            :check
              ?'Record standard check'
              :`Record ${action.replace('_',' ')}`
          }
        </button>
      }
    >
      {check
        ?(
          <div
            className={`sleep-banner ${
              sleeping.some(s=>s.status==='red')
                ?'red'
                :sleeping.some(s=>s.status==='amber')
                  ?'amber'
                  :'green'
            }`}
          >
            <b>{sleeping.length} sleeping</b>
            {' · '}
            worst status {
              sleeping.some(s=>s.status==='red')
                ?'red'
                :sleeping.some(s=>s.status==='amber')
                  ?'amber'
                  :'green'
            }
          </div>
        )
        :(
          <Choice
            label="Action"
            values={[
              'put_down',
              'fell_asleep',
              'wake',
              'got_up'
            ]}
            value={action}
            set={setAction}
          />
        )
      }

      {check&&
        <>
          <Choice
            label="Warmth"
            values={['normal','warm','cool']}
            value={warmth}
            set={setWarmth}
          />

          <Choice
            label="Breathing"
            values={['normal','changed']}
            value={breathing}
            set={setBreathing}
          />

          <Choice
            label="Wellbeing"
            values={['well','concern']}
            value={wellbeing}
            set={setWellbeing}
          />

          {sleeping.map(s=>
            <p key={s.id}>
              <b>{s.child_name}</b>
              {' · '}
              {s.last_check_at
                ?`last ${new Date(s.last_check_at).toLocaleTimeString()}`
                :'first check due'
              }
              {' · '}
              {s.next_due_at
                ?`next ${new Date(s.next_due_at).toLocaleTimeString()}`
                :''
              }
              {' · '}
              <span className={s.status}>
                {s.status}
              </span>
            </p>
          )}
        </>
      }

      {!check&&
        sessions
          .filter(s=>s.stale)
          .map(s=>
            <p className="recovered" key={s.id}>
              <b>{s.child_name}</b>: {s.stale_reason}.
              {' '}Select “got up” to reconcile explicitly.
            </p>
          )
      }

      <label>
        Optional note
        <input
          value={note}
          onChange={e=>setNote(e.target.value)}
        />
      </label>

      <EffectiveTime
        value={time}
        onChange={setTime}
      />
    </WorkflowWorkspace>
  );
}
