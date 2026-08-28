import React,{useEffect,useMemo,useState}from'react';
import{api}from'../api';

type Child={
  id:string;
  first_name:string;
  last_name:string;
};

type Attendance={
  id:string;
  arrived_at?:string|null;
  departed_at?:string|null;
  room?:string|null;
};

type Sleep={
  id:string;
  put_down_at?:string|null;
  fell_asleep_at?:string|null;
  woke_at?:string|null;
  got_up_at?:string|null;
  duration_minutes?:number|null;
  quality?:string|null;
  wake_state?:string|null;
  note?:string|null;
  room?:string|null;
};

type CareEvent={
  id:string;
  type:string;
  effective_at:string;
  data:any;
  room?:string|null;
};

type DayData={
  date:string;
  attendance:Attendance[];
  sleep_sessions:Sleep[];
  events:CareEvent[];
};

const icons:Record<string,string>={
  nappy:'🚽',
  toilet:'🚻',
  food:'🍽',
  sunscreen:'☀',
  medicine:'💊',
  incident:'⚠',
  staff_note:'📝'
};

function time(value?:string|null){
  if(!value)return '—';

  return new Date(value).toLocaleTimeString(
    'en-NZ',
    {
      hour:'numeric',
      minute:'2-digit'
    }
  );
}

function duration(minutes?:number|null){
  if(minutes===null||minutes===undefined)return '';

  if(minutes<60){
    return `${minutes} min`;
  }

  const hours=Math.floor(minutes/60);
  const mins=minutes%60;

  return mins
    ? `${hours} hr ${mins} min`
    : `${hours} hr`;
}

function niceArea(value:string){
  return value.replaceAll('_',' ');
}

function servingAmount(value:any){
  if(typeof value!=='number')return null;

  if(value===0)return 'none';
  if(value===.25)return '¼';
  if(value===.5)return '½';
  if(value===.75)return '¾';
  if(value===1)return 'all';

  return String(value);
}

function eventTitle(event:CareEvent){
  if(event.type==='nappy'||event.type==='toilet'){
    return 'Toileting';
  }

  if(event.type==='food'){
    return event.data?.meal||'Food';
  }

  if(event.type==='sunscreen'){
    return 'Sunscreen';
  }

  if(event.type==='medicine'){
    return event.data?.medication||'Medicine';
  }

  if(event.type==='incident'){
    return event.data?.incident_type||'Incident';
  }

  return event.type.replaceAll('_',' ');
}

function eventDetail(event:CareEvent){
  const d=event.data||{};

  switch(event.type){
    case'nappy':
      return [
        d.outcome,
        d.consistency,
        d.note
      ].filter(Boolean).join(' · ');

    case'toilet':
      return [
        d.what,
        d.outcome,
        d.clothing_changed?'clothing changed':null,
        d.note
      ].filter(Boolean).join(' · ');

    case'food':{
      const total=
        typeof d.total_servings==='number'
          ? servingAmount(d.total_servings)
          : null;

      return [
        d.food,
        total?`${total} serving${d.total_servings===1?'':'s'}`:null,
        d.enjoyment
      ].filter(Boolean).join(' · ');
    }

    case'sunscreen':
      return [
        d.application,
        d.note
      ].filter(Boolean).join(' · ');

    case'medicine':
      return [
        d.dose,
        d.route,
        d.outcome?.replaceAll('_',' ')
      ].filter(Boolean).join(' · ');

    case'incident':
      return [
        d.description||d.incident_type,
        Array.isArray(d.body_areas)&&d.body_areas.length
          ? d.body_areas.map(niceArea).join(', ')
          : null,
        d.involved
      ].filter(Boolean).join(' · ');

    default:
      return Object.entries(d)
        .filter(([,value])=>
          value!==null &&
          value!==undefined &&
          value!=='' &&
          typeof value!=='object'
        )
        .map(([,value])=>String(value))
        .join(' · ');
  }
}

function dayString(date:Date){
  const y=date.getFullYear();
  const m=String(date.getMonth()+1).padStart(2,'0');
  const d=String(date.getDate()).padStart(2,'0');

  return `${y}-${m}-${d}`;
}

function moveDay(value:string,amount:number){
  const date=new Date(`${value}T12:00:00`);
  date.setDate(date.getDate()+amount);
  return dayString(date);
}

function todayString(){
  return dayString(new Date());
}

function displayDate(value:string){
  const date=new Date(`${value}T12:00:00`);

  const today=todayString();

  if(value===today)return 'Today';

  return date.toLocaleDateString(
    'en-NZ',
    {
      weekday:'short',
      day:'numeric',
      month:'short'
    }
  );
}

function updateLocation(child:string,day:string){
  const params=new URLSearchParams(location.search);
  params.set('child',child);
  params.set('day',day);

  history.replaceState(
    null,
    '',
    `${location.pathname}?${params.toString()}`
  );
}

function SleepRow({sleep}:{sleep:Sleep}){
  const visibleStart=
    sleep.fell_asleep_at ||
    sleep.put_down_at;

  const visibleEnd=
    sleep.woke_at ||
    sleep.got_up_at;

  return(
    <details className="parent-sleep-row">
      <summary>
        <span className="day-icon">😴</span>

        <span className="day-main">
          <b>Sleep</b>

          {sleep.duration_minutes!==null &&
           sleep.duration_minutes!==undefined &&
            <small>{duration(sleep.duration_minutes)}</small>
          }
        </span>

        <time>
          {time(visibleStart)}
          {visibleEnd&&` – ${time(visibleEnd)}`}
        </time>

        <span className="expand-arrow">⌄</span>
      </summary>

      <div className="sleep-expanded">
        <SleepMoment
          label="Put down"
          value={sleep.put_down_at}
        />

        <SleepMoment
          label="Fell asleep"
          value={sleep.fell_asleep_at}
        />

        <SleepMoment
          label="Woke"
          value={sleep.woke_at}
        />

        <SleepMoment
          label="Got up"
          value={sleep.got_up_at}
        />
      </div>

      {(sleep.quality||sleep.wake_state||sleep.note)&&
        <div className="sleep-extra">
          {sleep.quality&&
            <span>Quality: {sleep.quality}</span>
          }

          {sleep.wake_state&&
            <span>
              Wake state: {sleep.wake_state}
            </span>
          }

          {sleep.note&&
            <span>{sleep.note}</span>
          }
        </div>
      }
    </details>
  );
}

function SleepMoment({
  label,
  value
}:{
  label:string;
  value?:string|null;
}){
  return(
    <div>
      <small>{label}</small>
      <b>{time(value)}</b>
    </div>
  );
}

function CareRow({event}:{event:CareEvent}){
  const detail=eventDetail(event);

  return(
    <article className="parent-day-row">
      <span className="day-icon">
        {icons[event.type]||'•'}
      </span>

      <span className="day-main">
        <b>{eventTitle(event)}</b>

        {detail&&
          <small>{detail}</small>
        }
      </span>

      <time>{time(event.effective_at)}</time>
    </article>
  );
}

function AttendanceRow({
  type,
  value
}:{
  type:'Drop off'|'Pick up';
  value?:string|null;
}){
  if(!value)return null;

  return(
    <div className="attendance-row">
      <b>{type}</b>
      <time>{time(value)}</time>
    </div>
  );
}

export default function ParentView(){
  const[data,setData]=useState<any>();
  const[child,setChild]=useState('');
  const[day,setDay]=useState(
    new URLSearchParams(location.search).get('day')||
    todayString()
  );

  const[record,setRecord]=useState<DayData>();
  const[login,setLogin]=useState(false);
  const[note,setNote]=useState('');
  const[error,setError]=useState('');

  useEffect(()=>{
    void api('/parent/me')
      .then(me=>{
        setData(me);

        const requested=
          new URLSearchParams(location.search)
            .get('child');

        const remembered=
          localStorage.getItem('parent-child');

        const chosen=
          me.children.some((c:Child)=>c.id===requested)
            ? requested
            : me.children.some((c:Child)=>c.id===remembered)
              ? remembered
              : me.children[0]?.id;

        if(chosen){
          setChild(chosen);
          localStorage.setItem('parent-child',chosen);
          updateLocation(chosen,day);
        }
      })
      .catch(()=>setLogin(true));
  },[]);

  useEffect(()=>{
    if(!child)return;

    setRecord(undefined);
    setError('');

    void api(
      `/parent/children/${child}/day?day=${day}`
    )
      .then(setRecord)
      .catch(e=>setError(e.message));

    localStorage.setItem('parent-child',child);
    updateLocation(child,day);
  },[child,day]);

  const sleepRows=useMemo(
    ()=>(record?.sleep_sessions||[])
      .sort(
        (a,b)=>
          new Date(a.put_down_at||0).getTime()-
          new Date(b.put_down_at||0).getTime()
      ),
    [record]
  );

  const careRows=useMemo(
    ()=>(record?.events||[])
      .sort(
        (a,b)=>
          new Date(a.effective_at).getTime()-
          new Date(b.effective_at).getTime()
      ),
    [record]
  );

  const dropOff=
    record?.attendance
      ?.map(x=>x.arrived_at)
      .filter(Boolean)
      .sort()[0];

  const pickupValues=
    record?.attendance
      ?.map(x=>x.departed_at)
      .filter(Boolean)
      .sort()||[];

  const pickUp=
    pickupValues.length
      ? pickupValues[pickupValues.length-1]
      : null;

  const combined=useMemo(()=>{
    if(!record)return[];

    const rows:any[]=[
      ...careRows.map(event=>({
        kind:'event',
        time:event.effective_at,
        value:event
      })),

      ...sleepRows.map(sleep=>({
        kind:'sleep',
        time:
          sleep.fell_asleep_at||
          sleep.put_down_at||
          '',
        value:sleep
      }))
    ];

    return rows.sort(
      (a,b)=>
        new Date(a.time).getTime()-
        new Date(b.time).getTime()
    );
  },[record,careRows,sleepRows]);

  if(login){
    return(
      <main className="login">
        <h1>
          Parent session required
        </h1>

        <p>
          Return to the parent sign-in page and
          sign in again.
        </p>

        <button onClick={()=>
          location.assign('/parent')
        }>
          Return to sign in
        </button>
      </main>
    );
  }

  if(!data){
    return(
      <main className="loading">
        Loading daily record…
      </main>
    );
  }

  const selectedChild=
    data.children.find(
      (c:Child)=>c.id===child
    );

  const today=todayString();

  return(
    <main className="parent parent-day">
      <header>
        <strong>
          Essentials <i>Marked</i>
        </strong>

        <span>{data.centre}</span>
      </header>

      <nav className="parent-child-tabs">
        {data.children.map((c:Child)=>(
          <button
            key={c.id}
            className={c.id===child?'active':''}
            onClick={()=>setChild(c.id)}
          >
            {c.first_name}
          </button>
        ))}
      </nav>

      <section className="parent-day-heading">
        <div>
          <h1>
            {displayDate(day)} — {selectedChild?.first_name}
          </h1>

          <span>
            Daily care summary
          </span>
        </div>

        <div className="day-navigation">
          <button
            className="minor"
            onClick={()=>setDay(moveDay(day,-1))}
          >
            ←
          </button>

          <input
            aria-label="Day"
            type="date"
            value={day}
            max={today}
            onChange={e=>setDay(e.target.value)}
          />

          <button
            className="minor"
            disabled={day>=today}
            onClick={()=>setDay(moveDay(day,1))}
          >
            →
          </button>

          {day!==today&&
            <button
              className="minor"
              onClick={()=>setDay(today)}
            >
              Today
            </button>
          }
        </div>
      </section>

      {error&&
        <p className="error parent-status">
          {error}
        </p>
      }

      {!record&&!error&&
        <p className="parent-status">
          Loading…
        </p>
      }

      {record&&
        <section className="parent-story">
          <AttendanceRow
            type="Drop off"
            value={dropOff}
          />

          <div className="story-divider"/>

          {combined.length===0&&
            <p className="empty-day">
              No care records have been added for this day.
            </p>
          }

          {combined.map(row=>
            row.kind==='sleep'
              ?(
                <SleepRow
                  key={`sleep-${row.value.id}`}
                  sleep={row.value}
                />
              )
              :(
                <CareRow
                  key={`event-${row.value.id}`}
                  event={row.value}
                />
              )
          )}

          <div className="story-divider"/>

          {pickUp?
            <AttendanceRow
              type="Pick up"
              value={pickUp}
            />
            :
            dropOff&&
              <div className="attendance-row still-here">
                <b>Currently at centre</b>
                <span>Not yet picked up</span>
              </div>
          }
        </section>
      }

      <div className="parent-actions">
        <a
          href={
            `/api/parent/children/${child}/export`
          }
        >
          Download CSV record
        </a>
      </div>

      <section className="note">
        <h2>Note for the teachers</h2>

        <textarea
          value={note}
          onChange={e=>setNote(e.target.value)}
          placeholder={
            `Add a note about ${selectedChild?.first_name||'your child'}`
          }
        />

        <button
          disabled={!note.trim()}
          onClick={()=>
            api(
              '/parent/notes',
              {
                method:'POST',
                body:JSON.stringify({
                  child_id:child,
                  body:note.trim()
                })
              }
            ).then(()=>setNote(''))
          }
        >
          Send note
        </button>
      </section>
    </main>
  );
}