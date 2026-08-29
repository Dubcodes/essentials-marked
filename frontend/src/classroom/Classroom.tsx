import React,{useEffect,useState}from'react';
import{api}from'../api';
import{loadSnapshot,saveSnapshot,sync}from'../offline';
import{currentRoomPresentIds}from'../presence';
import{Food,Sunscreen,Toileting}from'./OrdinaryWorkflows';
import{
  SleepWorkflow,
  sleepCounts,
  type SleepSession
}from'./Sleep';
import{Medication}from'./Medication';
import{Incident}from'./Incident';
import{Presence}from'./Presence';
import{ParentNotes}from'./ParentNotes';
import{ClassroomHelp}from'./ClassroomHelp';
import type{Bootstrap,WorkflowProps}from'./types';

type View=
  'toileting'|
  'sunscreen'|
  'food'|
  'sleep'|
  'sleep-check'|
  'medicine'|
  'incident'|
  'presence'|
  'notes'|
  'emergency'|
  'sync'|
  'help'|
  '';

type SleepAction=
  'put_down'|
  'fell_asleep'|
  'wake'|
  'got_up';

export const restoreContext=(data:Bootstrap)=>({
  roomId:
    data.rooms.some(
      r=>r.id===localStorage.getItem('classroom-room')
    )
      ? localStorage.getItem('classroom-room')!
      : data.default_room_id||
        data.rooms[0]?.id||
        '',

  staffId:
    data.staff.some(
      s=>s.id===localStorage.getItem('classroom-staff')
    )
      ? localStorage.getItem('classroom-staff')!
      : data.staff[0]?.id||
        ''
});

export default function Classroom(){
  const[data,setData]=useState<Bootstrap>();
  const[roomId,setRoomState]=useState('');
  const[staffId,setStaffState]=useState('');
  const[view,setView]=useState<View>('');
  const[sleepAction,setSleepAction]=
    useState<SleepAction>('put_down');

  const[notice,setNotice]=useState('');
  const[syncState,setSyncState]=useState('Synced');
  const[sleeps,setSleeps]=useState<SleepSession[]>([]);
  const[meds,setMeds]=useState<any[]>([]);
  const[wake,setWake]=useState('Wake lock starting');
  const[offlineSnapshot,setOfflineSnapshot]=useState(false);

  const refresh=async()=>{
    const[
      boot,
      sleep,
      medications
    ]=await Promise.all([
      api('/classroom/bootstrap'),
      api('/classroom/sleep-status'),
      api('/classroom/medications')
    ]);

    setData(boot);
    setSleeps(sleep.sessions);
    setMeds(medications);
    const confirmedAt=new Date().toISOString();
    await saveSnapshot('classroom-emergency',{centre:boot.centre,rooms:boot.rooms,children:boot.children.map((child:any)=>({id:child.id,first_name:child.first_name,last_name:child.last_name,room_id:child.room_id,present:child.present,visiting_room_id:child.visiting_room_id,arrived_at:child.arrived_at})),default_room_id:boot.default_room_id,confirmedAt});
    setOfflineSnapshot(false);

    return boot;
  };

  useEffect(()=>{
    void refresh()
      .then(boot=>{
        const context=restoreContext(boot);
        setRoomState(context.roomId);
        setStaffState(context.staffId);
      })
      .catch(async(error:any)=>{
        if(error?.status===401||error?.status===403){location.assign('/classroom/pair');return}
        const cached=await loadSnapshot('classroom-emergency');
        if(cached?.value){const snapshot=cached.value;const boot={device_id:'offline',default_room_id:snapshot.default_room_id,rooms:snapshot.rooms,staff:[],children:snapshot.children,unread_notes:0,centre:snapshot.centre,last_confirmed_at:snapshot.confirmedAt};setData(boot);setSleeps([]);setMeds([]);const context=restoreContext(boot);setRoomState(context.roomId);setStaffState('');setSyncState('Offline · cached roll');setOfflineSnapshot(true)}
      });
  },[]);

  useEffect(()=>{
    let lock:any;

    const acquire=async()=>{
      try{
        if(
          'wakeLock' in navigator &&
          document.visibilityState==='visible'
        ){
          lock=await(
            navigator as any
          ).wakeLock.request('screen');

          setWake('Screen awake');
        }else{
          setWake('Wake Lock unsupported');
        }
      }catch{
        setWake('Wake Lock unavailable');
      }
    };

    const visible=()=>{
      if(document.visibilityState==='visible'){
        void acquire();
      }
    };

    void acquire();

    document.addEventListener(
      'visibilitychange',
      visible
    );

    return()=>{
      document.removeEventListener(
        'visibilitychange',
        visible
      );

      void lock?.release();
    };
  },[]);

  useEffect(()=>{
    const run=async()=>{
      const state=await sync();

      setSyncState(
        state.unreachable
          ?state.pending?`Offline · ${state.pending} pending`:'Offline'
          :state.needsAttention
          ?'Needs attention'
          :state.pending
            ?`${state.pending} pending`
            :'Synced'
      );
    };

    const online=()=>void run();
    const offline=()=>setSyncState('Offline');

    addEventListener('online',online);
    addEventListener('offline',offline);
    addEventListener('outbox-change',online);

    void run();

    const timer=setInterval(run,15000);

    return()=>{
      removeEventListener('online',online);
      removeEventListener('offline',offline);
      removeEventListener('outbox-change',online);
      clearInterval(timer);
    };
  },[]);

  const setRoom=(id:string)=>{
    localStorage.setItem('classroom-room',id);
    setRoomState(id);
    setView('');
  };

  const setStaff=(id:string)=>{
    localStorage.setItem('classroom-staff',id);
    setStaffState(id);
  };

  const openSleep=(action:SleepAction)=>{
    setSleepAction(action);
    setView('sleep');
  };

  if(!data){
    return(
      <main className="loading">
        Opening classroom console…
      </main>
    );
  }

  const counts=sleepCounts(sleeps,roomId);

  const present=
    currentRoomPresentIds(
      data.children,
      roomId
    ).length;

  const visiting=
    data.children.filter(
      c=>
        c.present &&
        c.visiting_room_id===roomId
    ).length;

  const medicationActive=
    meds.filter(
      m=>m.received&&!m.returned_at
    ).length;

  const workflow:WorkflowProps={
    data,
    roomId,
    staffId,
    close:()=>setView(''),
    refresh:async()=>{
      await refresh();
    },
    notice:setNotice
  };

  return(
    <main className="classroom">
      <header>
        <div>
          {data.centre?.logo_url&&<img className="brand-logo" src={data.centre.logo_url} alt=""/>}<strong>{data.centre?.display_name||<>Essentials <i>Marked</i></>}</strong>{data.centre?.secondary_text&&<small>{data.centre.secondary_text}</small>}

          <select
            aria-label="Current room"
            value={roomId}
            onChange={e=>setRoom(e.target.value)}
          >
            {data.rooms.map(r=>(
              <option
                key={r.id}
                value={r.id}
              >
                {r.name}
              </option>
            ))}
          </select>
        </div>

        <div className="staff">
          <select
            aria-label="Selected staff"
            value={staffId}
            onChange={e=>setStaff(e.target.value)}
          >
            {data.staff.map(s=>(
              <option
                key={s.id}
                value={s.id}
              >
                {s.name}
              </option>
            ))}
          </select>

          <em
            className={
              syncState==='Synced'
                ?'ok'
                :'warn'
            }
          >
            {syncState}
          </em>

          <button
            className="minor"
            title={wake}
            onClick={()=>
              document.documentElement
                .requestFullscreen?.()
            }
          >
            ⛶ Fullscreen
          </button>
        </div>
      </header>

      <div className="console">
        <section className="metrics">

          <Metric
            value={present}
            label="physically here"
            onClick={()=>setView('presence')}
          />

          <Metric
            value={visiting}
            label="visiting"
            onClick={()=>setView('presence')}
          />

          <Metric
            value={counts.settling}
            label="settling"
            onClick={()=>
              openSleep('fell_asleep')
            }
          />

          <Metric
            value={counts.sleeping}
            label="sleeping"
            onClick={()=>
              setView('sleep-check')
            }
          />

          <Metric
            value={counts.worst}
            label="sleep checks"
            tone={counts.worst}
            onClick={()=>
              setView('sleep-check')
            }
          />

          <Metric
            value={medicationActive}
            label="medication active"
            onClick={()=>
              setView('medicine')
            }
          />

          <Metric
            value={data.unread_notes}
            label="unread notes"
            onClick={()=>
              setView('notes')
            }
          />

          <Metric
            value={syncState}
            label="sync"
            onClick={()=>setView('sync')}
          />

        </section>

        {notice&&
          <p
            className="notice"
            role="status"
          >
            {notice}
          </p>
        }

        <h1>
          {data.rooms.find(
            r=>r.id===roomId
          )?.name} classroom
        </h1>

        <section className="actions">
          {([
            ['toileting','🚽','Toileting'],
            ['sleep','😴','Sleep'],
            ['sleep-check','✓','Sleep Check'],
            ['food','🍽','Food'],
            ['sunscreen','☀','Sunscreen'],
            ['medicine','💊','Medicine'],
            ['incident','⚠','Incident / Injury / Illness'],
            ['presence','↔','Attendance / Presence']
          ]as const).map(
            ([id,icon,label])=>(
              <button
                key={id}
                onClick={()=>{
                  if(id==='sleep'){
                    openSleep('put_down');
                  }else{
                    setView(id);
                  }
                }}
              >
                <span>{icon}</span>
                {label}

                {id==='sleep-check'&&
                  <small>
                    {counts.sleeping} sleeping · {counts.worst}
                  </small>
                }
              </button>
            )
          )}
        </section>

        <p><button className="minor" onClick={()=>setView('emergency')}>Emergency roll</button> <button className="minor" onClick={()=>setView('help')}>Help</button></p>

        <p className="wake-state">
          {wake}
        </p>
      </div>

      {view==='toileting'&&
        <Toileting {...workflow}/>
      }

      {view==='sunscreen'&&
        <Sunscreen {...workflow}/>
      }

      {view==='food'&&
        <Food {...workflow}/>
      }

      {view==='sleep'&&
        <SleepWorkflow
          {...workflow}
          initialAction={sleepAction}
        />
      }

      {view==='sleep-check'&&
        <SleepWorkflow
          {...workflow}
          check
        />
      }

      {view==='medicine'&&
        <Medication {...workflow}/>
      }

      {view==='incident'&&
        <Incident {...workflow}/>
      }

      {view==='presence'&&
        <Presence {...workflow}/>
      }

      {view==='notes'&&
        <ParentNotes {...workflow}/>
      }
      {view==='emergency'&&<EmergencyRoll data={data} offline={offlineSnapshot||syncState==='Offline'} close={()=>setView('')}/>}
      {view==='sync'&&<div className="sheet" role="dialog" aria-modal="true"><section><button className="close" onClick={()=>setView('')}>×</button><h2>Sync details</h2><p>{syncState}</p><p>Ordinary care records queue automatically during retryable outages. Medication and incident finalisation require a live connection.</p></section></div>}
      {view==='help'&&<div className="workflow-workspace" role="dialog" aria-modal="true" aria-label="Classroom help"><section className="workflow-panel workflow-single"><header className="workflow-header"><h2>Classroom Help</h2><button className="close" onClick={()=>setView('')}>×</button></header><div className="workflow-body"><div className="workflow-details"><ClassroomHelp/></div></div><footer className="workflow-footer"><button className="minor" onClick={()=>setView('')}>Close</button></footer></section></div>}
    </main>
  );
}

function EmergencyRoll({data,offline,close}:{data:Bootstrap;offline:boolean;close:()=>void}){const confirmed=new Date(data.last_confirmed_at||Date.now());const stale=Date.now()-confirmed.getTime()>12*60*60*1000;const present=data.children.filter(c=>c.present);const groups=data.rooms.map(room=>({room,children:present.filter(c=>(c.visiting_room_id||c.room_id)===room.id)})).filter(group=>group.children.length);return <div className="emergency-overlay" role="dialog" aria-modal="true" aria-label="Emergency roll"><section className="emergency-roll"><div className="no-print"><button className="close" onClick={close}>×</button></div><h1>{data.centre?.display_name||'Essentials Marked'} — Emergency roll</h1>{offline&&<p className="offline-banner">OFFLINE — LAST KNOWN ROSTER</p>}{stale&&<p className="offline-banner">STALE — confirm against another source</p>}<p>Generated {new Date().toLocaleString()} · last confirmed {confirmed.toLocaleString()}</p>{groups.map(({room,children})=><section key={room.id}><h2>{room.name}</h2>{children.map(child=><p key={child.id}>☐ {child.first_name} {child.last_name}</p>)}</section>)}{!present.length&&<p>No children were marked present at the last confirmation.</p>}<button className="no-print" onClick={()=>print()}>Print emergency roll</button></section></div>}

function Metric({
  value,
  label,
  tone,
  onClick
}:{
  value:string|number;
  label:string;
  tone?:string;
  onClick?:()=>void;
}){
  const className=`metric ${tone||''}`;

  if(onClick){
    return(
      <button
        type="button"
        className={className}
        onClick={onClick}
      >
        <b>{value}</b>
        <span>{label}</span>
      </button>
    );
  }

  return(
    <div className={className}>
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}
