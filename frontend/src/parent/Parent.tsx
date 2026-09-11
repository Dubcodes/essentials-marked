import React,{useEffect,useMemo,useState}from'react';
import{api}from'../api';
import{useLiveReconciliation}from'../live';
import{DismissibleOverlay}from'../ui/DismissibleOverlay';

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
  source?:string|null;late_sign_in?:boolean;staff?:string|null;sign_out_staff?:string|null;device?:string|null;relationship?:string|null;signature_available?:boolean;sign_in_relationship?:string|null;sign_out_relationship?:string|null;sign_in_signature_available?:boolean;sign_out_signature_available?:boolean;sign_in_signature_purpose?:'kiosk_sign_in'|'parent_missing_sign_in_confirmation'|null;sign_out_signature_purpose?:'kiosk_sign_out'|'parent_missing_sign_out_confirmation'|null;
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
type ChildAlert={id:string;label:string;type:string};

type DayData={
  date:string;
  attendance:Attendance[];
  sleep_sessions:Sleep[];
  events:CareEvent[];
  alerts?:ChildAlert[];
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
export const canRequestOlderRecord=(status?:number,message='')=>status===403&&message.includes('history window');

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

export function attendanceDisplayTime(value:string|undefined|null,selectedDay:string,timezone='Pacific/Auckland'){
  if(!value)return '—';
  const instant=new Date(value);const parts=Object.fromEntries(new Intl.DateTimeFormat('en-NZ',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(instant).map(part=>[part.type,part.value]));const localDay=[parts.year,parts.month,parts.day].join('-');
  return localDay===selectedDay?instant.toLocaleTimeString('en-NZ',{timeZone:timezone,hour:'numeric',minute:'2-digit'}):instant.toLocaleString('en-NZ',{timeZone:timezone,day:'numeric',month:'short',hour:'numeric',minute:'2-digit'});
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
        ,Array.isArray(d.actions)?d.actions.map((a:any)=>`${a.action_at?time(a.action_at):'time recorded'} ${a.description||a}`).join(', '):null
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

export const attendancePresentation=(type:'Drop off'|'Pick up',value:Attendance)=>{
  const signIn=type==='Drop off';
  return{
    source:signIn
      ?value.sign_in_signature_purpose==='parent_missing_sign_in_confirmation'?'Teacher sign-in / Parent confirmed':value.late_sign_in?'Teacher late sign-in':value.source==='parent_kiosk'?'Parent sign-in':value.source==='classroom'?'Teacher sign-in':value.source?.replaceAll('_',' ')||''
      :value.sign_out_signature_purpose==='parent_missing_sign_out_confirmation'?'Teacher sign-out / Parent confirmed':value.sign_out_signature_available?'Parent sign-out':'Teacher sign-out',
    relationship:signIn?(value.sign_in_relationship??value.relationship):value.sign_out_relationship,
    staff:signIn?value.staff:value.sign_out_signature_purpose==='parent_missing_sign_out_confirmation'?value.sign_out_staff:null,
    signatureAvailable:signIn?(value.sign_in_signature_available??value.signature_available):value.sign_out_signature_available,
    purpose:signIn?(value.sign_in_signature_purpose||'kiosk_sign_in'):(value.sign_out_signature_purpose||'kiosk_sign_out')
  };
};

function AttendanceRow({
  type,
  value,onSignature,selectedDay,timezone
}:{
  type:'Drop off'|'Pick up';
  value?:Attendance|null;selectedDay:string;timezone:string;onSignature:(id:string,purpose:'kiosk_sign_in'|'parent_missing_sign_in_confirmation'|'kiosk_sign_out'|'parent_missing_sign_out_confirmation',meta:any)=>void;
}){
  const at=type==='Drop off'?value?.arrived_at:value?.departed_at;if(!value||!at)return null;
  const{source,relationship,staff,signatureAvailable,purpose}=attendancePresentation(type,value);

  return(
    <div className="attendance-row">
      <b>{type}</b>
      <time>{attendanceDisplayTime(at,selectedDay,timezone)}</time><small>{[value.room,relationship,staff?`Entered by ${staff}`:null,!staff?value.device:null,source].filter(Boolean).join(' · ')}</small>{signatureAvailable&&<button className="minor" onClick={()=>onSignature(value.id,purpose,{type,at,relationship,room:value.room})}>View signature</button>}
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
  const[errorStatus,setErrorStatus]=useState<number>();
  const[requestState,setRequestState]=useState<'idle'|'sending'|'sent'>('idle');
  const[signature,setSignature]=useState<any>();
  const[relationships,setRelationships]=useState<any[]>([]);
  const[newRelationship,setNewRelationship]=useState('');
  const loadRelationships=()=>api('/parent/relationships').then(setRelationships).catch(()=>undefined);
  const openSignature=(id:string,purpose:string,meta:any)=>void api('/parent/attendance/'+id+'/signature?purpose='+purpose).then((result:any)=>setSignature({...result,...meta,purpose}));

  const reconcile=async()=>{
    const me=await api('/parent/me');
    setData(me);
    const available=me.children.some((item:Child)=>item.id===child);
    const selected=available?child:me.children[0]?.id;
    if(selected&&selected!==child){setChild(selected);return;}
    if(selected){
      const next=await api(`/parent/children/${selected}/day?day=${day}`);
      setRecord(next);
    }
  };
  const liveState=useLiveReconciliation(reconcile);

  useEffect(()=>{
    void api('/parent/me')
      .then(me=>{
        setData(me);
        if(!new URLSearchParams(location.search).get('day')&&me.today)setDay(me.today);

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
  useEffect(()=>{void loadRelationships()},[]);

  useEffect(()=>{
    if(!child)return;

    setRecord(undefined);
    setError('');
    setErrorStatus(undefined);setRequestState('idle');

    void api(
      `/parent/children/${child}/day?day=${day}`
    )
      .then(setRecord)
      .catch(e=>{setError(e.message);setErrorStatus(e.status)});

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

  const dropOff=record?.attendance?.filter(x=>x.arrived_at).sort((a,b)=>String(a.arrived_at).localeCompare(String(b.arrived_at)))[0];

  const pickupValues=
    record?.attendance?.filter(x=>x.departed_at).sort((a,b)=>String(a.departed_at).localeCompare(String(b.departed_at)))||[];

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

  const today=data.today||todayString();

  return(
    <main className="parent parent-day">
      <header>
        {data.logo_url&&<img className="brand-logo" src={data.logo_url} alt=""/>}
        <strong>{data.display_name||<>Essentials <i>Marked</i></>}</strong>
        <span>{data.secondary_text||data.centre}</span>
        <small className={liveState==='Live'?'live-indicator':'live-indicator offline'}>{liveState}</small>
        <button className="minor" onClick={()=>void api('/auth/logout',{method:'POST'}).finally(()=>location.reload())}>Sign out</button>
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
        <section className="parent-status"><p className="error">{error}</p>{errorStatus===403&&error.includes('history window')&&<>{requestState==='sent'?<p className="notice">Request sent to the centre.</p>:<><p>Older records can be requested from the centre.</p><button disabled={requestState==='sending'} onClick={()=>{setRequestState('sending');void api('/parent/data-requests',{method:'POST',body:JSON.stringify({child_id:child,start_date:day,end_date:day,note:'Requested from daily record view'})}).then(()=>setRequestState('sent')).catch(e=>{setRequestState('idle');setError(e.message);setErrorStatus(e.status)})}}>{requestState==='sending'?'Sending…':'Request this date'}</button></>}</>}</section>
      }

      {!record&&!error&&
        <p className="parent-status">
          Loading…
        </p>
      }

      {record&&
        <>{record.alerts&&record.alerts.length>0&&<section className="parent-alerts" aria-label="Current child alerts">{record.alerts.map(alert=><p key={alert.id}><b>{alert.label}</b> — please speak with your teachers if you need more detail.</p>)}</section>}<section className="parent-story">
          <AttendanceRow
            type="Drop off"
            value={dropOff}
            selectedDay={day}
            timezone={data.timezone}
            onSignature={openSignature}
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
              selectedDay={day}
              timezone={data.timezone}
              onSignature={openSignature}
            />
            :
            dropOff&&
              <div className="attendance-row still-here">
                <b>Currently at centre</b>
                <span>Not yet picked up</span>
              </div>
          }
        </section></>
      }

      <details className="parent-relationships">
        <summary><h2>Sign-in relationships · {relationships.filter(option=>option.active).length} active</h2></summary>
        <p>These are available for future kiosk sign-ins. Removing one keeps past attendance unchanged.</p>
        <div className="person-list">{relationships.map(option=><div className="person-row" key={option.id}><span><b>{option.label}</b><small>{option.active?'Active':'Inactive'}</small></span><button className="minor" onClick={()=>{if(window.confirm(`${option.active?'Remove':'Restore'} ${option.label} ${option.active?'from future sign-in choices?':'for future sign-in choices?'}`))void api(`/parent/relationships/${option.id}`,{method:'PATCH',body:JSON.stringify({active:!option.active})}).then(loadRelationships)}}>{option.active?'Remove':'Restore'}</button></div>)}</div>
        <div className="inline"><input aria-label="Add sign-in relationship" value={newRelationship} onChange={event=>setNewRelationship(event.target.value)} placeholder="Add relationship"/><button disabled={!newRelationship.trim()} onClick={()=>void api('/parent/relationships',{method:'POST',body:JSON.stringify({label:newRelationship.trim()})}).then(()=>{setNewRelationship('');return loadRelationships()})}>+ Add relationship</button></div>
      </details>
      {signature&&<DismissibleOverlay onClose={()=>setSignature(undefined)} label="Signature" panelClass="compact-signature-modal parent-signature-modal"><button type="button" className="close" aria-label="Close signature" onClick={()=>setSignature(undefined)}>×</button><h2>Signature</h2><img className="signature-view" src={signature.signature_data} alt="Parent attendance signature"/><h3>{signature.type}</h3><p>{new Date(signature.at||signature.signed_at).toLocaleString('en-NZ',{timeZone:data.timezone})}</p>{signature.relationship&&<p>Relationship: {signature.relationship}</p>}{signature.room&&<p>Room: {signature.room}</p>}</DismissibleOverlay>}

      <div className="parent-actions">
        <a
          href={
            `/api/parent/children/${child}/export?day=${day}`
          }
        >
          Download this day (CSV)
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
      <details className="parent-help"><summary>Help</summary><h2>Using your daily record</h2><p>Choose a child at the top, then use the arrows or date box to change day.</p><p>Drop off is when your child arrived. Pick up is when they left. Select View signature to see the saved attendance confirmation.</p><p>Daily care entries show meals, sleep, toileting and other updates shared by Teachers. Sign-in relationships control the choices offered on the sign-in tablet.</p><p>Use Note for the teachers to send a message. Download this day saves the selected day as a spreadsheet-friendly CSV file.</p><p>If a sign-out was missed, the sign-in tablet will ask you to confirm the actual pickup date and time before the next sign-in.</p><p>Records are available from {data.oldest_online_date}; ask the centre for anything older.</p></details>
    </main>
  );
}
